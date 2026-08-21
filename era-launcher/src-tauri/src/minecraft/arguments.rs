use crate::prelude::*;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct ArgumentBuilder;

impl ArgumentBuilder {
    pub fn collect_args(
        args: &[serde_json::Value],
        features: &std::collections::HashMap<String, bool>,
    ) -> Vec<String> {
        let mut result = Vec::new();
        for arg in args {
            match arg {
                serde_json::Value::String(s) => result.push(s.clone()),
                serde_json::Value::Object(map) => {
                    if let Some(rule_value) = map.get("rules") {
                        if Self::rules_apply(rule_value, features) {
                            if let Some(value) = map.get("value") {
                                match value {
                                    serde_json::Value::String(s) => result.push(s.clone()),
                                    serde_json::Value::Array(arr) => {
                                        for v in arr {
                                            if let Some(s) = v.as_str() {
                                                result.push(s.to_string());
                                            }
                                        }
                                    }
                                    _ => {}
                                }
                            }
                        }
                    }
                }
                _ => {}
            }
        }
        result
    }

    pub fn build_jvm_args(args: &[String], memory: u32) -> Vec<String> {
        args.iter()
            .map(|a| a.replace("${MAX_MEMORY}", &memory.to_string()))
            .collect()
    }

    pub fn substitute_tokens(args: &[String], tokens: &[(String, String)]) -> Vec<String> {
        args.iter()
            .map(|arg| {
                let mut result = arg.clone();
                for (key, value) in tokens {
                    result = result.replace(&format!("${{{}}}", key), value);
                }
                result
            })
            .collect()
    }

    fn rules_apply(
        rules: &serde_json::Value,
        features: &std::collections::HashMap<String, bool>,
    ) -> bool {
        let rules_arr = match rules.as_array() {
            Some(a) => a,
            None => return true,
        };
        let mut allowed = false;
        let mut matched = false;
        for rule in rules_arr {
            let obj = match rule.as_object() {
                Some(o) => o,
                None => continue,
            };
            let action = obj
                .get("action")
                .and_then(|a| a.as_str())
                .unwrap_or("allow");
            let os = obj.get("os").and_then(|o| o.as_object());
            let mut rule_ok = true;
            if let Some(os) = os {
                if let Some(name) = os.get("name").and_then(|n| n.as_str()) {
                    let current = match std::env::consts::OS {
                        "windows" => "windows",
                        "macos" => "osx",
                        _ => "linux",
                    };
                    if current != name {
                        rule_ok = false;
                    }
                }
            }

            if let Some(features_rule) = obj.get("features").and_then(|f| f.as_object()) {
                for (k, v) in features_rule {
                    let v_bool = match v {
                        serde_json::Value::Bool(b) => *b,
                        _ => continue,
                    };
                    if v_bool {
                        if !features.get(k).copied().unwrap_or(false) {
                            rule_ok = false;
                        }
                    }
                }
            }

            matched = true;
            if rule_ok {
                allowed = action == "allow";
            }
        }
        matched && allowed
    }
}
