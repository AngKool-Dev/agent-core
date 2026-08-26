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
                    if v_bool && !features.get(k).copied().unwrap_or(false) {
                        rule_ok = false;
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

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::HashMap;

    fn parse_json(s: &str) -> serde_json::Value {
        serde_json::from_str(s).unwrap()
    }

    #[test]
    fn test_collect_args_plain_strings() {
        let args = vec![
            parse_json("\"hello\""),
            parse_json("\"-Xmx4G\""),
            parse_json("\"--demo\""),
        ];
        let features = HashMap::new();
        let result = ArgumentBuilder::collect_args(&args, &features);
        assert_eq!(result, vec!["hello", "-Xmx4G", "--demo"]);
    }

    #[test]
    fn test_collect_args_with_rules() {
        let args = vec![
            parse_json(
                "{\"rules\":[{\"action\":\"allow\",\"os\":{\"name\":\"windows\"}}],\"value\":\"win-only\"}",
            ),
            parse_json("\"always\""),
        ];
        let features = HashMap::new();
        let result = ArgumentBuilder::collect_args(&args, &features);
        if cfg!(windows) {
            assert_eq!(result, vec!["win-only", "always"]);
        } else {
            assert_eq!(result, vec!["always"]);
        }
    }

    #[test]
    fn test_substitute_tokens() {
        let args = vec![
            "--username ${auth_player_name}".to_string(),
            "--version ${version_name}".to_string(),
        ];
        let tokens = vec![
            ("auth_player_name".to_string(), "Steve".to_string()),
            ("version_name".to_string(), "1.21.1".to_string()),
        ];
        let result = ArgumentBuilder::substitute_tokens(&args, &tokens);
        assert_eq!(result, vec!["--username Steve", "--version 1.21.1"]);
    }

    #[test]
    fn test_substitute_tokens_no_match() {
        let args = vec!["--username ${auth_player_name}".to_string()];
        let tokens: Vec<(String, String)> = vec![];
        let result = ArgumentBuilder::substitute_tokens(&args, &tokens);
        assert_eq!(result, vec!["--username ${auth_player_name}"]);
    }

    #[test]
    fn test_rules_apply_empty() {
        let features = HashMap::new();
        let rules = parse_json("[]");
        let result = ArgumentBuilder::rules_apply(&rules, &features);
        assert!(!result);
    }

    #[test]
    fn test_rules_apply_no_rules() {
        let features = HashMap::new();
        let v = parse_json("null");
        let result = ArgumentBuilder::rules_apply(&v, &features);
        assert!(result);
    }
}
