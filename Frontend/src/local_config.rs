// Config local del usuario en ~/.misyks/config — mismo archivo y formato que
// lee Backend/sec/mail/config.py. Aqui vive porque la app es quien lo crea y
// lo edita (pantalla de Ajustes); el agente Python solo lo consume.
use std::collections::BTreeMap;
use std::path::PathBuf;

pub struct LocalConfig {
    path: PathBuf,
    sections: BTreeMap<String, BTreeMap<String, String>>,
}

impl LocalConfig {
    pub fn data_dir() -> PathBuf {
        let home = std::env::var("HOME").expect("HOME no esta definido");
        PathBuf::from(home).join(".misyks")
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
        std::fs::write(&self.path, out)?;
        restringir_permisos(&self.path)
    }
}

#[cfg(unix)]
fn restringir_permisos(path: &std::path::Path) -> std::io::Result<()> {
    use std::os::unix::fs::PermissionsExt;
    std::fs::set_permissions(path, std::fs::Permissions::from_mode(0o600))
}

#[cfg(not(unix))]
fn restringir_permisos(_path: &std::path::Path) -> std::io::Result<()> {
    Ok(())
}

fn generar_clave_hex() -> String {
    // 32 bytes de /dev/urandom (getrandom via el propio SO), sin depender de
    // ninguna crate de criptografia adicional solo para esto.
    let bytes = leer_aleatorios(32);
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

#[cfg(unix)]
fn leer_aleatorios(n: usize) -> Vec<u8> {
    use std::io::Read;
    let mut f = std::fs::File::open("/dev/urandom").expect("no se pudo abrir /dev/urandom");
    let mut buf = vec![0u8; n];
    f.read_exact(&mut buf).expect("fallo leyendo /dev/urandom");
    buf
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
