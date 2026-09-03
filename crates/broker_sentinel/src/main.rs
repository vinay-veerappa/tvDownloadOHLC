//! broker_sentinel binary entrypoint.

use broker_sentinel::run_main;

#[tokio::main]
async fn main() {
    run_main().await;
}