//! Size limits.

/// Elements checked per validation block when copying input. A block is
/// small enough to stay in L1 cache between the check and the copy.
pub const VALIDATION_BLOCK_LEN: usize = 64;
