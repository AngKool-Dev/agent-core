use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum AccountType {
    Offline,
    Microsoft,
}

impl Default for AccountType {
    fn default() -> Self {
        AccountType::Offline
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Account {
    pub id: String,
    pub name: String,
    pub uuid: String,
    #[serde(rename = "type")]
    pub account_type: AccountType,
    pub access_token: Option<String>,
    pub created_at: i64,
    pub last_used: Option<i64>,
}

impl Account {
    pub fn new_offline(name: String) -> Self {
        let uuid = format!("{:032x}", rand::random::<u128>());
        Self {
            id: uuid.clone(),
            name,
            uuid,
            account_type: AccountType::Offline,
            access_token: None,
            created_at: chrono::Utc::now().timestamp(),
            last_used: None,
        }
    }
}

impl Default for Account {
    fn default() -> Self {
        Self::new_offline("Player".to_string())
    }
}

pub fn is_valid_username(name: &str) -> bool {
    let len = name.chars().count();
    (3..=16).contains(&len) && name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
}
