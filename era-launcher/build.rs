use std::env;
use std::path::Path;
use std::process::Command;

fn main() {
    let out_dir = env::var("OUT_DIR").unwrap();
    let obj_file = Path::new(&out_dir).join("era-launcher_res.o");

    let manifest_dir = env::var("CARGO_MANIFEST_DIR").unwrap();
    let rc_file = Path::new(&manifest_dir).join("src/resources/era-launcher.rc");

    if rc_file.exists() {
        let windres = "C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\WinGet\\Packages\\BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe\\mingw64\\bin\\windres.exe";
        let output = Command::new(windres)
            .current_dir(&manifest_dir)
            .arg(rc_file.strip_prefix(&manifest_dir).unwrap_or(Path::new("src/resources/era-launcher.rc")))
            .arg("-o")
            .arg(&obj_file)
            .output()
            .expect("Failed to execute windres");

        if output.status.success() {
            println!("cargo:rustc-link-arg={}", obj_file.display());
        }
    }
}
