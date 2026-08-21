use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstanceConfig {
    pub id: String,
    pub name: String,
    pub game_version: String,
    pub loader: String,
    pub loader_version: Option<String>,
    pub memory: u32,
    pub java: Option<String>,
    pub game_dir: Option<String>,
    pub resolution_width: Option<u32>,
    pub resolution_height: Option<u32>,
    pub account_uuid: Option<String>,
    pub minecraft_dir: Option<String>,
}

impl Default for InstanceConfig {
    fn default() -> Self {
        Self {
            id: uuid::Uuid::new_v4().to_string(),
            name: "New Instance".to_string(),
            game_version: "1.21.1".to_string(),
            loader: "vanilla".to_string(),
            loader_version: None,
            memory: 4096,
            java: None,
            game_dir: None,
            resolution_width: None,
            resolution_height: None,
            account_uuid: None,
            minecraft_dir: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InstanceManager {
    pub instances: Vec<InstanceConfig>,
}

impl InstanceManager {
    pub fn new() -> Self {
        Self { instances: Vec::new() }
    }

    pub fn list(&self) -> &[InstanceConfig] {
        &self.instances
    }

    pub fn get(&self, id: &str) -> Option<&InstanceConfig> {
        self.instances.iter().find(|i| i.id == id)
    }

    pub fn get_mut(&mut self, id: &str) -> Option<&mut InstanceConfig> {
        self.instances.iter_mut().find(|i| i.id == id)
    }

    pub fn add(&mut self, instance: InstanceConfig) {
        self.instances.push(instance);
    }

    pub fn remove(&mut self, id: &str) -> bool {
        let initial = self.instances.len();
        self.instances.retain(|i| i.id != id);
        self.instances.len() != initial
    }

    pub fn update(&mut self, instance: InstanceConfig) -> bool {
        if let Some(i) = self.instances.iter_mut().find(|i| i.id == instance.id) {
            *i = instance;
            true
        } else {
            false
        }
    }
}
