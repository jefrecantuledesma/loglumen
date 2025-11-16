use actix_cors::Cors;
use actix_web::{web, App, HttpResponse, HttpServer, Result};
use parking_lot::RwLock;
use percent_encoding::percent_decode_str;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::{Path, PathBuf};
use std::sync::Arc;

// Event structure matching Python agent JSON schema
#[derive(Debug, Clone, Serialize, Deserialize)]
struct Event {
    schema_version: u32,
    category: String,
    event_type: String,
    time: String,
    host: String,
    host_ipv4: String,
    os: String,
    source: String,
    severity: String,
    message: String,
    data: serde_json::Value,
}

// Statistics for frontend
#[derive(Debug, Serialize)]
struct CategoryStats {
    category: String,
    total_count: usize,
    event_types: HashMap<String, usize>,
    severity_counts: HashMap<String, usize>,
    recent_events: Vec<Event>,
}

#[derive(Debug, Serialize)]
struct DashboardStats {
    total_events: usize,
    categories: Vec<CategoryStats>,
    last_updated: String,
    nodes: Vec<NodeStats>,
}

#[derive(Debug, Serialize)]
struct NodeStats {
    host: String,
    host_ipv4: String,
    total_events: usize,
    last_event_time: Option<String>,
    categories: HashMap<String, usize>,
    severity_counts: HashMap<String, usize>,
}

// Application state
struct AppState {
    events: Arc<RwLock<Vec<Event>>>,
}

// POST /api/events - Receive events from agent
async fn receive_events(
    events: web::Json<Vec<Event>>,
    data: web::Data<AppState>,
) -> Result<HttpResponse> {
    let mut store = data.events.write();

    println!("[INFO] Received {} events", events.len());

    for event in events.iter() {
        println!("  [{}] {} - {}",
            event.category,
            event.event_type,
            event.message
        );
        store.push(event.clone());
    }

    println!("[OK] Total events stored: {}", store.len());

    Ok(HttpResponse::Ok().json(serde_json::json!({
        "status": "success",
        "received": events.len()
    })))
}

// GET /api/stats - Get statistics for dashboard
async fn get_stats(data: web::Data<AppState>) -> Result<HttpResponse> {
    let store = data.events.read();

    // Group events by category
    let mut category_map: HashMap<String, Vec<Event>> = HashMap::new();
    let mut node_map: HashMap<String, NodeStats> = HashMap::new();

    for event in store.iter() {
        category_map
            .entry(event.category.clone())
            .or_insert_with(Vec::new)
            .push(event.clone());

        let node_key = format!("{}|{}", event.host, event.host_ipv4);
        let node = node_map.entry(node_key).or_insert_with(|| NodeStats {
            host: event.host.clone(),
            host_ipv4: event.host_ipv4.clone(),
            total_events: 0,
            last_event_time: None,
            categories: HashMap::new(),
            severity_counts: HashMap::new(),
        });

        node.total_events += 1;
        node.last_event_time = Some(event.time.clone());
        *node.categories.entry(event.category.clone()).or_insert(0) += 1;
        *node.severity_counts.entry(event.severity.clone()).or_insert(0) += 1;
    }

    // Build category statistics
    let mut categories = Vec::new();

    for (category, events) in category_map.iter() {
        // Count event types
        let mut event_types: HashMap<String, usize> = HashMap::new();
        for event in events {
            *event_types.entry(event.event_type.clone()).or_insert(0) += 1;
        }

        // Count severities
        let mut severity_counts: HashMap<String, usize> = HashMap::new();
        for event in events {
            *severity_counts.entry(event.severity.clone()).or_insert(0) += 1;
        }

        // Get recent events (last 10)
        let recent_events: Vec<Event> = events
            .iter()
            .rev()
            .take(10)
            .cloned()
            .collect();

        categories.push(CategoryStats {
            category: category.clone(),
            total_count: events.len(),
            event_types,
            severity_counts,
            recent_events,
        });
    }

    // Sort categories by name
    categories.sort_by(|a, b| a.category.cmp(&b.category));

    let mut nodes: Vec<NodeStats> = node_map.into_values().collect();
    nodes.sort_by(|a, b| b.total_events.cmp(&a.total_events).then_with(|| a.host.cmp(&b.host)));

    let stats = DashboardStats {
        total_events: store.len(),
        categories,
        last_updated: chrono::Utc::now().to_rfc3339(),
        nodes,
    };

    Ok(HttpResponse::Ok().json(stats))
}

// GET /api/events - Get all events (for debugging)
async fn get_all_events(data: web::Data<AppState>) -> Result<HttpResponse> {
    let store = data.events.read();
    Ok(HttpResponse::Ok().json(&*store))
}

// GET /api/events/{host} - Get events for a specific host
async fn get_events_for_host(
    host: web::Path<String>,
    data: web::Data<AppState>,
) -> Result<HttpResponse> {
    let decoded = percent_decode_str(&host.into_inner())
        .decode_utf8_lossy()
        .to_string();

    let store = data.events.read();
    let mut events: Vec<Event> = store
        .iter()
        .filter(|event| event.host == decoded)
        .cloned()
        .collect();

    events.reverse(); // Latest events at the top

    Ok(HttpResponse::Ok().json(events))
}

// GET / - Serve dashboard HTML
async fn serve_dashboard() -> Result<HttpResponse> {
    let html = include_str!("../static/index.html");
    Ok(HttpResponse::Ok()
        .content_type("text/html; charset=utf-8")
        .body(html))
}

// GET /style.css - Serve CSS
async fn serve_css() -> Result<HttpResponse> {
    let css = include_str!("../static/style.css");
    Ok(HttpResponse::Ok()
        .content_type("text/css; charset=utf-8")
        .body(css))
}

// GET /dashboard.js - Serve JavaScript
async fn serve_js() -> Result<HttpResponse> {
    let js = include_str!("../static/dashboard.js");
    Ok(HttpResponse::Ok()
        .content_type("application/javascript; charset=utf-8")
        .body(js))
}

// GET /node.html - Serve node detail page
async fn serve_node_page() -> Result<HttpResponse> {
    let html = include_str!("../static/node.html");
    Ok(HttpResponse::Ok()
        .content_type("text/html; charset=utf-8")
        .body(html))
}

// GET /node.js - Serve node detail JavaScript
async fn serve_node_js() -> Result<HttpResponse> {
    let js = include_str!("../static/node.js");
    Ok(HttpResponse::Ok()
        .content_type("application/javascript; charset=utf-8")
        .body(js))
}

fn load_bind_address() -> String {
    if let Ok(addr) = std::env::var("LOGLUMEN_BIND_ADDRESS") {
        println!("[CONFIG] Using bind address from LOGLUMEN_BIND_ADDRESS");
        return addr;
    }

    let configured_path = std::env::var("LOGLUMEN_SERVER_CONFIG")
        .unwrap_or_else(|_| "config/server.toml".to_string());

    if let Some(addr) = read_bind_address_from_path(&configured_path) {
        return addr;
    }

    if configured_path != "config/server.example.toml" {
        if let Some(addr) = read_bind_address_from_path("config/server.example.toml") {
            return addr;
        }
    }

    "0.0.0.0:8080".to_string()
}

fn read_bind_address_from_path<P: AsRef<Path>>(path: P) -> Option<String> {
    let path_ref = path.as_ref();
    let candidate: PathBuf = if path_ref.is_dir() {
        path_ref.join("server.toml")
    } else {
        path_ref.to_path_buf()
    };

    let contents = std::fs::read_to_string(&candidate).ok()?;
    parse_bind_address(&contents).map(|addr| {
        println!("[CONFIG] Using bind address from {}", candidate.display());
        addr
    })
}

fn parse_bind_address(contents: &str) -> Option<String> {
    for line in contents.lines() {
        let trimmed = line.trim();
        if trimmed.is_empty() || trimmed.starts_with('#') || trimmed.starts_with('[') {
            continue;
        }

        if let Some(value_part) = trimmed.strip_prefix("bind_address") {
            let value_part = value_part.trim_start();
            if !value_part.starts_with('=') {
                continue;
            }

            let mut value = value_part[1..].trim();
            if value.starts_with('"') && value.ends_with('"') && value.len() >= 2 {
                value = &value[1..value.len() - 1];
            }

            if !value.is_empty() {
                return Some(value.to_string());
            }
        }
    }

    None
}

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let bind_address = load_bind_address();

    let separator = "=".repeat(70);
    println!("{}", separator);
    println!("Loglumen Server Starting");
    println!("{}", separator);
    println!("Listening on: http://{}", bind_address);
    println!("Dashboard: http://{}/", bind_address);
    println!("API endpoint: http://{}/api/events", bind_address);
    println!("Stats endpoint: http://{}/api/stats", bind_address);
    println!("{}", separator);

    // Create shared state
    let app_state = web::Data::new(AppState {
        events: Arc::new(RwLock::new(Vec::new())),
    });

    // Start HTTP server
    HttpServer::new(move || {
        // Configure CORS to allow requests from any origin
        let cors = Cors::permissive();

        App::new()
            .wrap(cors)
            .app_data(app_state.clone())
            // API routes
            .route("/api/events", web::post().to(receive_events))
            .route("/api/stats", web::get().to(get_stats))
            .route("/api/events", web::get().to(get_all_events))
            .route("/api/events/{host}", web::get().to(get_events_for_host))
            // Frontend routes
            .route("/", web::get().to(serve_dashboard))
            .route("/node.html", web::get().to(serve_node_page))
            .route("/style.css", web::get().to(serve_css))
            .route("/dashboard.js", web::get().to(serve_js))
            .route("/node.js", web::get().to(serve_node_js))
    })
    .bind(bind_address)?
    .run()
    .await
}
