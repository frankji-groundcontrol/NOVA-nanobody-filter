//! Public unsupported-mode/argument failures must remain explicit before any output mutation.
use std::process::Command;

#[test]
fn unsupported_dynamic_mode_is_an_input_error() {
    let output = Command::new(env!("CARGO_BIN_EXE_aggrescan3d-rs"))
        .arg("--dynamic")
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("only static scoring"));
}

#[test]
fn missing_inputs_do_not_start_surface_calculation() {
    let output = Command::new(env!("CARGO_BIN_EXE_aggrescan3d-rs"))
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("Required option"));
}
