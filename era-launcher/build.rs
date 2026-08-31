use std::env;
use std::path::Path;
use std::process::Command;

fn main() {
    let out_dir = env::var("OUT_DIR").unwrap();
    let obj_file = Path::new(&out_dir).join("era-launcher_res.o");

    let manifest_dir = env::var("CARGO_MANIFEST_DIR").unwrap();
    let rc_file = Path::new(&manifest_dir).join("src/resources/era-launcher.rc");

    if rc_file.exists() {
        let windres = find_windres();
        if let Some(windres) = windres {
            let output = Command::new(&windres)
                .current_dir(&manifest_dir)
                .arg(
                    rc_file
                        .strip_prefix(&manifest_dir)
                        .unwrap_or(Path::new("src/resources/era-launcher.rc")),
                )
                .arg("-o")
                .arg(&obj_file)
                .output();

            if let Ok(output) = output {
                if output.status.success() {
                    println!("cargo:rustc-link-arg={}", obj_file.display());
                }
            }
        }
    }
}

fn find_windres() -> Option<std::path::PathBuf> {
    if let Ok(p) = std::env::var("WINDRES_PATH") {
        return Some(std::path::PathBuf::from(p));
    }
    let output = Command::new("windres").arg("--version").output();
    if output.map(|o| o.status.success()).unwrap_or(false) {
        Some(std::path::PathBuf::from("windres"))
    } else {
        None
    }
}
