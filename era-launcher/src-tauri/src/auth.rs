use md5::{Digest, Md5};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
#[derive(Default)]
pub enum AccountType {
    #[default]
    Offline,
    Microsoft,
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
        let uuid = offline_uuid(&name);
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

/// Minecraft username rules: 3–16 chars, [A-Za-z0-9_].
pub fn is_valid_username(name: &str) -> bool {
    let len = name.chars().count();
    (3..=16).contains(&len) && name.chars().all(|c| c.is_ascii_alphanumeric() || c == '_')
}

/// Derive the deterministic OFFLINE player UUID exactly like the official
/// launcher/Minecraft does:
///
/// ```text
/// UUID.nameUUIDFromBytes(("OfflinePlayer:" + name).getBytes(UTF_8))
/// ```
///
/// This is an MD5-based version-3 UUID. A RANDOM uuid (the previous
/// behaviour) made every launch a different "player", breaking skins and
/// per-player server state.
pub fn offline_uuid(name: &str) -> String {
    let mut hasher = Md5::new();
    hasher.update(format!("OfflinePlayer:{}", name).as_bytes());
    let digest = hasher.finalize();
    let mut bytes = [0u8; 16];
    bytes.copy_from_slice(&digest);

    // Set version 3 (MD5 hash) in the high nibble of byte 6…
    bytes[6] = (bytes[6] & 0x0f) | 0x30;
    // …and the RFC 4122 variant (10xx) in the top bits of byte 8.
    bytes[8] = (bytes[8] & 0x3f) | 0x80;

    format!(
        "{:02x}{:02x}{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}-{:02x}{:02x}{:02x}{:02x}{:02x}{:02x}",
        bytes[0],
        bytes[1],
        bytes[2],
        bytes[3],
        bytes[4],
        bytes[5],
        bytes[6],
        bytes[7],
        bytes[8],
        bytes[9],
        bytes[10],
        bytes[11],
        bytes[12],
        bytes[13],
        bytes[14],
        bytes[15]
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_offline_uuid_is_deterministic_v3() {
        let a = offline_uuid("Notch");
        let b = offline_uuid("Notch");
        assert_eq!(a, b, "same name must always derive the same uuid");

        // Canonical UUID layout: 8-4-4-4-12 lowercase hex.
        let parts: Vec<&str> = a.split('-').collect();
        assert_eq!(parts.len(), 5);
        assert_eq!(
            parts.iter().map(|p| p.len()).collect::<Vec<_>>(),
            vec![8, 4, 4, 4, 12]
        );
        // Version 3 nibble.
        assert_eq!(parts[2].chars().next().unwrap(), '3');
        // RFC 4122 variant.
        assert!(matches!(
            parts[3].chars().next().unwrap(),
            '8' | '9' | 'a' | 'b'
        ));
    }

    #[test]
    fn test_offline_uuid_differs_per_name() {
        assert_ne!(offline_uuid("Notch"), offline_uuid("jeb_"));
        // The name is mixed into the hash input.
        assert_ne!(offline_uuid("Steve"), offline_uuid("teve"));
    }

    #[test]
    fn test_is_valid_username() {
        assert!(is_valid_username("Notch"));
        assert!(is_valid_username("jeb_"));
        assert!(is_valid_username("abc"));
        assert!(!is_valid_username("ab")); // too short
        assert!(!is_valid_username("aaaaaaaaaaaaaaaaa")); // 17 chars
        assert!(!is_valid_username("has space"));
        assert!(!is_valid_username("no-hyphens"));
        assert!(!is_valid_username(""));
    }
}
