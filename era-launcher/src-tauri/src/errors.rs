use thiserror::Error;

#[derive(Error, Debug)]
pub enum LauncherError {
    #[error("Configuration error: {0}")]
    Config(String),

    #[error("Minecraft error: {0}")]
    Minecraft(String),

    #[error("Download error: {0}")]
    Download(String),

    #[error("Asset error: {0}")]
    Asset(String),

    #[error("Modrinth error: {0}")]
    Modrinth(String),

    #[error("Instance error: {0}")]
    Instance(String),

    #[error("Authentication error: {0}")]
    Auth(String),

    #[error("Process error: {0}")]
    Process(String),

    #[error("Java error: {0}")]
    Java(String),

    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Serialization error: {0}")]
    Serialization(#[from] serde_json::Error),

    #[error("HTTP error: {0}")]
    Http(#[from] reqwest::Error),

    #[error("UUID error: {0}")]
    Uuid(#[from] uuid::Error),

    #[error("Zip error: {0}")]
    Zip(String),

    #[error("Not found: {0}")]
    NotFound(String),
}

pub type Result<T> = std::result::Result<T, LauncherError>;
