//! Static Aggrescan3D port. See ../README.md for method/source and ../tests for parity.
pub mod accessibility;
pub mod error;
pub mod metrics;
pub mod parser;
pub mod pipeline;
pub mod report;
pub mod scoring;

pub type Result<T> = std::result::Result<T, error::Error>;
