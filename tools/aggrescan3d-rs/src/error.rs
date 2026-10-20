//! Typed CLI failures: input (2), external surface engine (3), filesystem (4), batch (5).
#[derive(Debug)]
pub enum Error {
    Input(String),
    External(String),
    Io(std::io::Error),
    Batch(String),
}
impl Error {
    pub fn exit_code(&self) -> i32 {
        match self {
            Self::Input(_) => 2,
            Self::External(_) => 3,
            Self::Io(_) => 4,
            Self::Batch(_) => 5,
        }
    }
}
impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Self::Input(s) | Self::External(s) | Self::Batch(s) => write!(f, "{s}"),
            Self::Io(e) => write!(f, "{e}"),
        }
    }
}
impl std::error::Error for Error {}
impl From<String> for Error {
    fn from(s: String) -> Self {
        Self::Input(s)
    }
}
impl From<&str> for Error {
    fn from(s: &str) -> Self {
        Self::Input(s.into())
    }
}
impl From<std::io::Error> for Error {
    fn from(e: std::io::Error) -> Self {
        Self::Io(e)
    }
}
impl From<std::num::ParseFloatError> for Error {
    fn from(e: std::num::ParseFloatError) -> Self {
        Self::Input(e.to_string())
    }
}
impl From<std::string::FromUtf8Error> for Error {
    fn from(e: std::string::FromUtf8Error) -> Self {
        Self::Input(e.to_string())
    }
}
impl From<std::str::Utf8Error> for Error {
    fn from(e: std::str::Utf8Error) -> Self {
        Self::Input(e.to_string())
    }
}
