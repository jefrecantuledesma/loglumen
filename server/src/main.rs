use actix_web::{web, App, HttpResponse, HttpServer, Result};
use actix_cors::Cors;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::Arc;
use parking_lot::RwLock;

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

    for event in store.iter() {
        category_map
            .entry(event.category.clone())
            .or_insert_with(Vec::new)
            .push(event.clone());
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

    let stats = DashboardStats {
        total_events: store.len(),
        categories,
        last_updated: chrono::Utc::now().to_rfc3339(),
    };

    Ok(HttpResponse::Ok().json(stats))
}

// GET /api/events - Get all events (for debugging)
async fn get_all_events(data: web::Data<AppState>) -> Result<HttpResponse> {
    let store = data.events.read();
    Ok(HttpResponse::Ok().json(&*store))
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

#[actix_web::main]
async fn main() -> std::io::Result<()> {
    let bind_address = "192.168.0.254:8080";

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
            // Frontend routes
            .route("/", web::get().to(serve_dashboard))
            .route("/style.css", web::get().to(serve_css))
            .route("/dashboard.js", web::get().to(serve_js))
    })
    .bind(bind_address)?
    .run()
    .await
}
