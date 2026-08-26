use std::env;
use std::process::{exit, Command};

fn main() {
    let binary = env::var_os("STRANDLINE_BIN").unwrap_or_else(|| "strandline".into());
    let status = Command::new(&binary)
        .args(env::args().skip(1))
        .status();
    match status {
        Ok(status) => exit(status.code().unwrap_or(1)),
        Err(error) => {
            eprintln!(
                "No se pudo ejecutar strandline ({:?}). Define STRANDLINE_BIN con la ruta al binario oficial: {}",
                binary, error
            );
            exit(127);
        }
    }
}
