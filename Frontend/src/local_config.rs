// Config local del usuario en ~/.misyks/config — mismo archivo y formato que
// lee Backend/sec/mail/config.py. Aqui vive porque la app es quien lo crea y
// lo edita (pantalla de Ajustes); el agente Python solo lo consume.
use std::collections::BTreeMap;
use std::path::PathBuf;

#[cfg(windows)]
use crate::proceso::sin_consola;

pub struct LocalConfig {
    path: PathBuf,
    sections: BTreeMap<String, BTreeMap<String, String>>,
}

impl LocalConfig {
    /// `~/.misyks`, resuelto igual que lo resuelve Python.
    ///
    /// Tiene que coincidir exactamente con `Path.home()` de `config.py`: si
    /// cada lado apunta a un directorio distinto, sec.mail sincroniza contra
    /// una base y la app abre otra, vacia, y encima sin error visible. Por eso
    /// se replica el orden de `os.path.expanduser("~")` de CPython en vez de
    /// usar solo HOME -- que en Windows no suele estar definido (y en git-bash
    /// lo esta, pero pudiendo apuntar a otra ruta).
    pub fn data_dir() -> PathBuf {
        home_dir().join(".misyks")
    }

    pub fn path() -> PathBuf {
        Self::data_dir().join("config")
    }

    pub fn load() -> Self {
        let path = Self::path();
        let sections = std::fs::read_to_string(&path)
            .map(|contents| parse_ini(&contents))
            .unwrap_or_default();
        Self { path, sections }
    }

    pub fn get(&self, section: &str, key: &str) -> Option<&str> {
        self.sections.get(section)?.get(key).map(String::as_str)
    }

    pub fn set(&mut self, section: &str, key: &str, value: &str) {
        self.sections
            .entry(section.to_string())
            .or_default()
            .insert(key.to_string(), value.to_string());
    }

    /// Clave hexadecimal de 64 caracteres que cifra sec_mail.db. La genera la
    /// app la primera vez que hace falta y la persiste — nunca se le pide al
    /// usuario que la escriba a mano.
    pub fn clave_db_o_generarla(&mut self) -> std::io::Result<String> {
        if let Some(existente) = self.get("secmail", "clave") {
            return Ok(existente.to_string());
        }
        let nueva = generar_clave_hex();
        self.set("secmail", "clave", &nueva);
        self.save()?;
        Ok(nueva)
    }

    /// Escribe el archivo restringiendo los permisos *antes* de volcar el
    /// contenido: se crea un temporal vacio, se le recortan los permisos, se
    /// escribe y solo entonces se renombra encima del definitivo.
    ///
    /// El orden importa. Escribir y restringir despues deja una ventana en la
    /// que la contrasena de Gmail y la clave de la base estan en disco con los
    /// permisos heredados; y si el recorte fallara, el secreto ya estaria
    /// escrito mientras la UI dice "no se pudo guardar". Con el temporal, un
    /// fallo significa que no se ha escrito nada y el mensaje es cierto.
    pub fn save(&self) -> std::io::Result<()> {
        std::fs::create_dir_all(Self::data_dir())?;
        let mut out = String::new();
        for (section, kvs) in &self.sections {
            out.push_str(&format!("[{section}]\n"));
            for (k, v) in kvs {
                out.push_str(&format!("{k} = {v}\n"));
            }
            out.push('\n');
        }

        let tmp = self.path.with_extension("tmp");
        let escribir = || -> std::io::Result<()> {
            std::fs::write(&tmp, "")?;
            restringir_permisos(&tmp)?;
            std::fs::write(&tmp, &out)?;
            // En Windows fs::rename reemplaza el destino existente
            // (MOVEFILE_REPLACE_EXISTING), igual que en Unix. Los permisos
            // recortados viajan con el archivo al renombrarlo.
            std::fs::rename(&tmp, &self.path)
        };
        let resultado = escribir();
        if resultado.is_err() {
            let _ = std::fs::remove_file(&tmp);
        }
        resultado
    }
}

#[cfg(unix)]
fn restringir_permisos(path: &std::path::Path) -> std::io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))
}

/// Equivalente en Windows del `0o600`: deja el archivo con un unico ACE, el de
/// la cuenta actual.
///
/// Sin esto el archivo hereda la ACL del perfil, que en una maquina real es
/// `NT AUTHORITY\SYSTEM`, `BUILTIN\Administrators` y el propio usuario, los
/// tres con FullControl (comprobado). Dentro estan la contrasena de aplicacion
/// de Gmail y la clave de `sec_mail.db`, asi que la premisa del diseno -- los
/// secretos no salen de la maquina del letrado -- pedia cerrarlo.
///
/// Se usa `icacls` en vez de la API Win32 (`SetNamedSecurityInfo`) para no
/// arrastrar `windows-sys` y varios bloques `unsafe` por un solo ajuste:
/// `/inheritance:r` borra los ACE heredados y `/grant:r` deja solo el nuestro.
#[cfg(windows)]
fn restringir_permisos(path: &std::path::Path) -> std::io::Result<()> {
    let usuario = match std::env::var("USERNAME") {
        Ok(u) if !u.is_empty() => u,
        _ => return Err(std::io::Error::other("USERNAME no esta definido")),
    };
    // Con dominio si lo hay; en cuentas locales USERDOMAIN es el nombre de la
    // maquina, que icacls resuelve igual de bien.
    let cuenta = match std::env::var("USERDOMAIN") {
        Ok(d) if !d.is_empty() => format!("{d}\\{usuario}"),
        _ => usuario,
    };

    let mut orden = std::process::Command::new("icacls");
    orden
        .arg(path)
        .arg("/inheritance:r")
        .arg("/grant:r")
        .arg(format!("{cuenta}:(F)"))
        .arg("/q");
    sin_consola(&mut orden);

    let salida = orden.output()?;
    if !salida.status.success() {
        return Err(std::io::Error::other(format!(
            "icacls no pudo restringir los permisos de {}: {}",
            path.display(),
            String::from_utf8_lossy(&salida.stderr).trim()
        )));
    }
    Ok(())
}

#[cfg(not(any(unix, windows)))]
fn restringir_permisos(_path: &std::path::Path) -> std::io::Result<()> {
    Ok(())
}

fn generar_clave_hex() -> String {
    let bytes = leer_aleatorios(32);
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

/// 32 bytes del RNG del sistema operativo.
///
/// Antes esto abria `/dev/urandom` a mano bajo `#[cfg(unix)]`, sin variante
/// para Windows: no era un fallo en ejecucion, es que el binario no compilaba
/// alli. `getrandom` hace la llamada nativa de cada plataforma y mantiene la
/// intencion original de no arrastrar una crate de criptografia entera.
///
/// Entra en panico si el SO no puede dar entropia: es la clave que cifra
/// sec_mail.db, asi que continuar con algo predecible seria peor que parar.
fn leer_aleatorios(n: usize) -> Vec<u8> {
    let mut buf = vec![0u8; n];
    getrandom::fill(&mut buf).expect("el SO no pudo generar numeros aleatorios");
    buf
}

/// Mismo orden de preferencia que `os.path.expanduser("~")` de CPython, que es
/// lo que hay detras de `Path.home()` en `Backend/sec/mail/config.py`.
#[cfg(windows)]
fn home_dir() -> PathBuf {
    if let Ok(perfil) = std::env::var("USERPROFILE") {
        return PathBuf::from(perfil);
    }
    if let (Ok(unidad), Ok(ruta)) = (std::env::var("HOMEDRIVE"), std::env::var("HOMEPATH")) {
        return PathBuf::from(format!("{unidad}{ruta}"));
    }
    panic!("no se pudo determinar el directorio del usuario: ni USERPROFILE ni HOMEDRIVE+HOMEPATH")
}

#[cfg(not(windows))]
fn home_dir() -> PathBuf {
    PathBuf::from(std::env::var("HOME").expect("HOME no esta definido"))
}

fn parse_ini(contents: &str) -> BTreeMap<String, BTreeMap<String, String>> {
    let mut sections: BTreeMap<String, BTreeMap<String, String>> = BTreeMap::new();
    let mut current = String::new();
    for line in contents.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') || line.starts_with(';') {
            continue;
        }
        if line.starts_with('[') && line.ends_with(']') {
            current = line[1..line.len() - 1].to_string();
            sections.entry(current.clone()).or_default();
        } else if let Some((k, v)) = line.split_once('=') {
            sections
                .entry(current.clone())
                .or_default()
                .insert(k.trim().to_string(), v.trim().to_string());
        }
    }
    sections
}
