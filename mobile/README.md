# XenoSys Mobile Application Architecture

## Overview

The XenoSys mobile application (iOS/Android) is a **thin client** - it does not process AI locally, but serves as a communication interface to the XenoSys backend.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Mobile App (React Native / Flutter)         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   Screens   │  │   State     │  │    API Client           │ │
│  │  - Chat     │  │  (Zustand/  │  │  - REST calls to        │ │
│  │  - Agents   │  │   Provider) │  │    Gateway              │ │
│  │  - Memory   │  │             │  │  - JWT auth             │ │
│  │  - Settings │  │             │  │  - WebSocket for       │ │
│  └─────────────┘  └─────────────┘  │    real-time           │ │
│                                      └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                     XenoSys Gateway (Server)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐ │
│  │   REST API  │  │   gRPC      │  │    WebSocket           │ │
│  │  /api/v1/*  │  │   Bridge    │  │    /ws/*               │ │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Thin Client Philosophy

- **No AI processing on device**: All LLM calls go through the Gateway
- **No local model storage**: Reduces app size significantly
- **Minimal local storage**: Only JWT tokens and server configuration

### 2. Authentication Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Login   │────▶│  Gateway │────▶│ Validate │────▶│  Issue   │
│  Screen  │     │  /auth   │     │  creds   │     │  JWT     │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                          │
                                                          ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Store   │◀────│  Secure  │◀────│  Refresh │◀────│  Token   │
│  in LS   │     │  Storage │     │  period  │     │  expiry  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

### 3. Feature Modules

#### Chat Interface
- Real-time message display via WebSocket
- Message history pagination
- Rich content support (markdown, code blocks)
- File/image attachments

#### Agent Management
- List available agents
- Configure agent parameters
- Switch between agents

#### Memory Viewer (2ndBrain / Obsidian)
- Read notes via Gateway REST API
- Search functionality
- Note metadata display
- Create new notes (send to Gateway)

#### Settings
- Server URL configuration
- Theme selection (light/dark)
- Notification preferences

### 4. Technology Choices

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | React Native | Cross-platform, large ecosystem |
| State | Zustand | Lightweight, TypeScript-friendly |
| HTTP Client | Axios | Interceptors, retry logic |
| Storage | react-native-keychain | Secure token storage |
| Real-time | Socket.io-client | WebSocket abstraction |

### 5. API Contract

```typescript
// Authentication
POST /api/v1/auth/login { email, password } → { token, refreshToken }
POST /api/v1/auth/refresh { refreshToken } → { token }
POST /api/v1/auth/logout → {}

// Agents
GET /api/v1/agents → [{ id, name, type, status }]
POST /api/v1/agents/:id/execute { message } → { response }

// Memory
GET /api/v1/memory/notes → [{ id, title, content, tags }]
POST /api/v1/memory/notes { title, content, tags } → { id }
GET /api/v1/memory/search?q=query → [{ id, title, score }]

// WebSocket
ws://server/ws/chat?token=...
```

## Security Considerations

1. **Token Storage**: Use Keychain/Keystore for JWT storage
2. **Certificate Pinning**: Pin Gateway SSL certificate
3. **Biometric Auth**: Optional biometric unlock for app
4. **Session Timeout**: Auto-logout after 30 days of inactivity

## Build & Deploy

```bash
# iOS
cd ios
pod install
xcodebuild -workspace XenoSys.xcworkspace

# Android
cd android
./gradlew assembleRelease
```

## Performance Targets

- App launch: < 2 seconds
- API response display: < 500ms (cached)
- WebSocket reconnection: < 1 second
- Memory footprint: < 100MB

## Future Enhancements

1. Push notifications for agent responses
2. Offline message queue
3. Background sync for memory
4. Widget support (iOS/Android)