use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LauncherInfo {
    pub main_class: String,
    pub arguments: Vec<String>,
}
