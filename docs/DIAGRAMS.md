# BetaGraph Diagrams

## 1. UML Class Diagram

Class structure and relationships across BetaGraph modules:

```mermaid
classDiagram
    class WTATrail {
        -name: str
        -slug: str
        -url: str
        -description: str
        -location: Location
        -length_mi: float
        -elevation_gain_ft: float
        -calculated_difficulty: str
        -features: list
        -alerts: list
        +to_searchable_text() str
    }

    class Location {
        -latitude: float
        -longitude: float
    }

    class TripReport {
        -description: str
        -date: str
        -condition: TripReportCondition
        -photos: list
    }

    class TripReportCondition {
        -type_of_hike: str
        -trail_conditions: str
        -road: str
        -bugs: str
        -snow: str
    }

    class WTAVectorStore {
        -client: ChromaClient
        -ef: EmbeddingFunction
        -collection: Collection
        +add_trails(trails) int
        +search(query, n_results, center_lat, center_lon, radius_miles) list
        +list_all() list
        +count() int
    }

    class Handlers {
        +get_store() WTAVectorStore
        +search_trails(query, location, ...) list
        +list_stored_trails() list
        +get_trail_count() int
        +scrape_region(location, radius_miles) dict
        +lazy_scrape_and_load(location, radius_miles) int
    }

    class WTAServer {
        <<FastMCP wta-trails>>
        +search_trails()
        +list_stored_trails()
        +get_trail_count()
        +geocode()
        +scrape_region()
    }

    class WeatherServer {
        <<FastMCP weather-forecast>>
        +get_weather_forecast()
    }

    class Agent {
        <<LangGraph + Gemini>>
        +create_agent_graph()
        +run_cli()
    }

    class MultiServerMCPClient {
        <<langchain_mcp_adapters>>
        +get_tools() LangChain tools
    }

    class SharedChroma {
        <<module>> shared/chroma
        +get_chroma_client()
        +get_embedding_function()
    }

    class geocode_forward {
        <<function>> geocode/geocode.py
        +geocode_forward(query, limit, country) list
    }

    class Scraper {
        <<module>> wta/scraper.py
        +scrape_wta_trails_for_location()
        +fetch_fresh_trail_info()
    }

    class fetch_forecast {
        <<function>> weather/forecast.py
        +fetch_forecast(lat, lon, days, units) dict
    }

    WTATrail *-- Location : contains
    WTATrail "1" *-- "0..*" TripReport : has
    TripReport *-- TripReportCondition : has

    WTAVectorStore ..> WTATrail : stores
    WTAVectorStore ..> SharedChroma : uses

    Handlers ..> WTAVectorStore : uses
    Handlers ..> geocode_forward : uses
    Handlers ..> Scraper : uses

    WTAServer ..> Handlers : delegates
    WTAServer ..> geocode_forward : geocode tool

    WeatherServer ..> fetch_forecast : calls

    Agent ..> MultiServerMCPClient : uses
    MultiServerMCPClient ..> WTAServer : MCP SSE
    MultiServerMCPClient ..> WeatherServer : MCP SSE
```

---

## 2. Architecture Mermaid Diagram

High-level system architecture, data flow, and deployment:

```mermaid
flowchart TB
    subgraph User["👤 User"]
        CLI[run_agent.py / beta-graph-agent CLI]
    end

    subgraph Agent["🤖 LangGraph Agent"]
        LLM[ChatGoogleGenerativeAI<br/>Gemini 2.5 Flash]
        AgentLogic[create_agent_graph<br/>System prompt + tools]
        LLM --> AgentLogic
    end

    subgraph MCP["MCP Client Layer"]
        MultiMCP[MultiServerMCPClient<br/>SSE transport]
        Tools[MCP Tools:<br/>search_trails, geocode,<br/>get_weather_forecast, etc.]
        MultiMCP --> Tools
    end

    subgraph Servers["MCP Servers (HTTP/SSE)"]
        subgraph WTA["WTA Server :8001"]
            WTAFastMCP[FastMCP wta-trails]
            Handlers[handlers]
            WTAFastMCP --> Handlers
        end

        subgraph Weather["Weather Server :8003"]
            WeatherFastMCP[FastMCP weather-forecast]
            Forecast[fetch_forecast]
            WeatherFastMCP --> Forecast
        end
    end

    subgraph WTA_Backend["WTA Backend"]
        ChromaStore[WTAVectorStore<br/>Chroma vector DB]
        Scraper[WTA Scraper<br/>Scrapling]
        Geocode[geocode_forward<br/>Google Places API]
        Handlers --> ChromaStore
        Handlers --> Scraper
        Handlers --> Geocode
    end

    subgraph External["External APIs"]
        OpenWeather[OpenWeatherMap API]
        GooglePlaces[Google Places API]
        WTAWebsite[WTA.org Website]
    end

    subgraph Storage["Storage"]
        Chroma[(Chroma<br/>Vector DB<br/>all-MiniLM-L6-v2)]
    end

    CLI --> AgentLogic
    AgentLogic --> MultiMCP
    Tools --> WTAFastMCP
    Tools --> WeatherFastMCP

    ChromaStore --> Chroma
    Scraper --> WTAWebsite
    Geocode --> GooglePlaces
    Forecast --> OpenWeather

    style Agent fill:#e1f5fe
    style MCP fill:#fff3e0
    style Servers fill:#f3e5f5
    style Storage fill:#e8f5e9
    style External fill:#fce4ec
```

---

### Deployment / Data Flow Sequence

```mermaid
sequenceDiagram
    participant U as User
    participant A as Agent (Gemini)
    participant MCP as MCP Client
    participant WTA as WTA Server
    participant W as Weather Server
    participant C as Chroma
    participant G as Google Places
    participant OWM as OpenWeatherMap
    participant Web as WTA.org

    Note over U,Web: One-time: load_wta_by_region.py / load_wta_to_chroma.py
    Web->>C: Scrape trails → Chroma

    Note over U,Web: Runtime: run_servers.py (WTA :8001, Weather :8003)
    U->>A: "easy hikes near North Bend"
    A->>MCP: get_tools()
    MCP->>WTA: search_trails(query, location)
    WTA->>G: geocode("North Bend, WA")
    G-->>WTA: lat, lon
    WTA->>C: vector search + radius filter
    C-->>WTA: trails
    opt lazy scrape
        WTA->>Web: scrape if few results
        Web-->>WTA: trails
        WTA->>C: add_trails()
    end
    WTA-->>A: trail results

    A->>MCP: get_weather_forecast(lat, lon)
    MCP->>W: fetch_forecast()
    W->>OWM: API call
    OWM-->>W: 5-day forecast
    W-->>A: forecast

    A-->>U: Formatted recommendation
```

---

### Component Overview

| Component | Technology | Role |
|-----------|------------|------|
| Agent | LangGraph + Gemini | Natural-language hiking planner |
| MCP Client | langchain-mcp-adapters | Connects agent to MCP servers via SSE |
| WTA Server | FastMCP | Trail search, geocode, lazy scrape |
| Weather Server | FastMCP | 5-day forecast |
| Chroma | Vector DB | Semantic search over trails |
| Embeddings | all-MiniLM-L6-v2 | Local sentence-transformers |
| Geocode | Google Places API | Place name → coordinates |
| Scraper | Scrapling (Fetcher) | WTA trail pages |
| Weather | OpenWeatherMap | Forecast data |
