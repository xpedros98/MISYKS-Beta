//! Lo que comparten las dos aplicaciones de MISYKS.
//!
//! Hay dos binarios: **`Frontend`**, la del abogado, y **`Frontend_Admin`**, la
//! de control -- ver `ARQUITECTURA.md` 8.5. Los dos hablan con el mismo Backend,
//! leen las mismas bases y se pintan con la misma paleta, asi que todo eso vive
//! aqui una sola vez.
//!
//! **La frontera es `Message`.** Lo que no lo menciona se puede compartir: el
//! acceso a datos, la invocacion del Backend, la configuracion local y los
//! estilos. Las pantallas no, porque cada aplicacion tiene sus mensajes y
//! meterlas aqui obligaria a inventar un tipo comun que no significa nada.
//!
//! Se comparte en un crate y no copiando ficheros por una razon concreta: dos
//! copias de `local_config.rs` acabarian escribiendo el mismo archivo de
//! secretos con reglas distintas, y ese archivo guarda el refresh token del
//! correo y la clave de las bases.

pub mod backend;
pub mod calendario;
pub mod estilo;
pub mod expedientes;
pub mod local_config;
pub mod proceso;
pub mod secretario;
