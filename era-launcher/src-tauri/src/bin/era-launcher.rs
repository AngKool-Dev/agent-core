// ARGUS Terminal UI entry point
// Usage: era-launcher [--instances-dir <path>] [--java-path <path>]

use clap::Parser;
use era_launcher_lib::argus::ArgusApp;

/// ARGUS — Terminal-native Minecraft runtime control for EraLauncher
#[derive(Parser, Debug)]
#[command(name = "era-launcher")]
#[command(about = "Terminal-native Minecraft runtime control for EraLauncher")]
struct Cli {
    /// Custom instances directory
    #[arg(long)]
    instances_dir: Option<String>,

    /// Custom Java path
    #[arg(long)]
    java_path: Option<String>,
}

fn main() -> anyhow::Result<()> {
    let cli = Cli::parse();

    if let Some(ref dir) = cli.instances_dir {
        eprintln!("Using instances directory: {}", dir);
    }
    if let Some(ref java) = cli.java_path {
        eprintln!("Using Java path: {}", java);
    }

    let mut app = ArgusApp::new()?;
    app.run()
}
