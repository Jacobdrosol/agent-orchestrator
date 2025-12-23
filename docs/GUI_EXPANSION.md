# GUI Expansion Guide

## Overview

This guide outlines the strategy for building a desktop GUI for the Agent Orchestrator. The GUI will provide visual monitoring, interactive control, and enhanced user experience while maintaining the CLI's functionality.

## Design Goals

1. **Visual Monitoring**: Real-time visualization of execution progress
2. **Interactive Control**: Start, pause, resume, and abort runs
3. **Historical Analysis**: Browse past runs and their results
4. **Configuration Management**: Edit settings visually
5. **Cross-Platform**: Support Windows, macOS, and Linux
6. **Lightweight**: Minimal resource overhead
7. **Accessibility**: Keyboard navigation and screen reader support

## Technology Stack

### Recommended: Electron + React

**Pros:**
- Cross-platform by default
- Rich ecosystem of UI components
- Web technologies (familiar to many developers)
- Easy integration with Python backend
- Active community and good documentation

**Cons:**
- Larger application size
- Higher memory usage
- Need to bundle runtime

### Alternative: PyQt/PySide

**Pros:**
- Native look and feel
- Lower memory footprint
- Python-native (no language boundary)
- Mature and stable

**Cons:**
- Steeper learning curve
- More verbose code
- License considerations (Qt licensing)

### Selected: Electron + React + TypeScript

We recommend Electron for better cross-platform support and modern UI capabilities.

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                     Electron Main Process                   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              IPC Communication Layer                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                            ↕                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Python Backend Bridge                    │  │
│  │  - Spawn Python process                              │  │
│  │  - Send commands via stdin/socket                    │  │
│  │  - Receive results via stdout/socket                 │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
                            ↕
┌────────────────────────────────────────────────────────────┐
│                  Python Orchestrator Process                │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              REST API / JSON-RPC Server               │  │
│  └──────────────────────────────────────────────────────┘  │
│                            ↕                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Orchestrator Core (existing)                │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
                            ↕
┌────────────────────────────────────────────────────────────┐
│                   Electron Renderer Process                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                  React Application                    │  │
│  │  - Dashboard                                          │  │
│  │  - Run Monitor                                        │  │
│  │  - History Browser                                    │  │
│  │  - Settings Editor                                    │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

## UI Components

### 1. Dashboard View

**Purpose**: Overview of system status and recent activity

**Components:**
- System status indicator (Ollama connection, database health)
- Quick start button for new tasks
- Recent runs list (last 10)
- Active runs with progress bars
- Statistics cards (total runs, success rate, avg duration)

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ Agent Orchestrator                        [_] [□] [X]   │
├─────────────────────────────────────────────────────────┤
│ [Dashboard] [Active] [History] [Settings]               │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Status: ● Running      Ollama: ● Connected             │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │ [Start New Task]                               │    │
│  │ ┌────────────────────────────────────────────┐ │    │
│  │ │ Enter task description...                  │ │    │
│  │ └────────────────────────────────────────────┘ │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Active Runs                                             │
│  ┌────────────────────────────────────────────────┐    │
│  │ Fix memory leak (Phase 2/3)         [Pause]   │    │
│  │ ████████████░░░░░░░░░░░░░░ 67%                │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Recent Runs                                             │
│  ┌────────────────────────────────────────────────┐    │
│  │ ✓ Add search functionality    2 hours ago      │    │
│  │ ✓ Update user model           5 hours ago      │    │
│  │ ✗ Fix API endpoints           1 day ago        │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 2. Active Run Monitor

**Purpose**: Detailed view of currently executing run

**Components:**
- Phase timeline (visual representation)
- Current phase details
- Live log viewer
- Findings counter (by severity)
- Pause/Resume/Abort controls
- Artifact list

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ Run: Add authentication system          [Pause] [Abort] │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Timeline                                                │
│  ┌─────┐     ┌─────┐     ┌─────┐     ┌─────┐          │
│  │  1  │────→│  2  │════→│  3  │─ ─ ─│  4  │          │
│  └─────┘     └─────┘     └─────┘     └─────┘          │
│    ✓           ▶           pending    pending          │
│  Setup      Backend      Tests       Deploy            │
│                                                          │
│  Current Phase: Backend Implementation                   │
│  ┌────────────────────────────────────────────────┐    │
│  │ Status: In Progress (Attempt 1/3)              │    │
│  │ Started: 2 minutes ago                         │    │
│  │ Estimated: 5 minutes remaining                 │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Findings: ⚠ 0 Major  ● 2 Medium  ○ 5 Minor            │
│                                                          │
│  Live Log                          [Auto-scroll] [Copy] │
│  ┌────────────────────────────────────────────────┐    │
│  │ [14:23:01] Starting phase execution...         │    │
│  │ [14:23:02] Retrieved context from RAG...       │    │
│  │ [14:23:05] Generated execution plan...         │    │
│  │ [14:23:15] Creating models/user.py...          │    │
│  │ [14:23:20] Running tests...                    │    │
│  │ ▌                                               │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 3. History Browser

**Purpose**: Browse and analyze past runs

**Components:**
- Run list with filters (status, date range, task text)
- Detailed view for selected run
- Phase breakdown
- Findings list
- Artifacts download
- Export options (JSON, Markdown)

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ Run History                                              │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Filters: [All Status ▾] [Last 30 Days ▾] [Search...]   │
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │ ✓ Add search functionality                     │    │
│  │   2024-12-20 14:23 | 3 phases | 15 min         │    │
│  ├────────────────────────────────────────────────┤    │
│  │ ✓ Update user authentication                   │◀──  │
│  │   2024-12-20 10:15 | 2 phases | 8 min          │    │
│  ├────────────────────────────────────────────────┤    │
│  │ ✗ Fix API rate limiting                        │    │
│  │   2024-12-19 16:40 | 4 phases | Failed at 2    │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Run Details: Update user authentication                 │
│  ┌────────────────────────────────────────────────┐    │
│  │ Status: ✓ Completed                            │    │
│  │ Duration: 8 minutes 23 seconds                 │    │
│  │ Findings: 0 Major, 1 Medium, 3 Minor           │    │
│  │                                                 │    │
│  │ Phases:                                         │    │
│  │  ✓ Phase 1: Update models (2 min)             │    │
│  │  ✓ Phase 2: Add validation (6 min)            │    │
│  │                                                 │    │
│  │ [View Findings] [Download Artifacts] [Export]  │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### 4. Settings Editor

**Purpose**: Visual configuration management

**Components:**
- Tabbed interface for config sections
- Form inputs with validation
- Reset to defaults button
- Save/Cancel actions
- Config file path display

**Layout:**
```
┌─────────────────────────────────────────────────────────┐
│ Settings                                  [Save] [Cancel]│
├─────────────────────────────────────────────────────────┤
│ [Execution] [Verification] [RAG] [Git] [Advanced]       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Execution Settings                                      │
│  ┌────────────────────────────────────────────────┐    │
│  │ Max Retries:        [3____________]            │    │
│  │                                                 │    │
│  │ Enable Copilot:     [✓] Yes  [ ] No            │    │
│  │                                                 │    │
│  │ Copilot Mode:       [Suggest ▾]                │    │
│  │                     - Suggest                   │    │
│  │                     - Execute                   │    │
│  │                     - Hybrid                    │    │
│  │                                                 │    │
│  │ Timeout (seconds):  [300__________]            │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Findings Thresholds                                     │
│  ┌────────────────────────────────────────────────┐    │
│  │ Max Major:          [0____________]            │    │
│  │ Max Medium:         [5____________]            │    │
│  │ Max Minor:          [20___________]            │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Config file: config/orchestrator-config.local.yaml     │
│  [Reset to Defaults]                                     │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Implementation Phases

### Phase 1: Backend API (Week 1-2)

**Goal**: Create JSON-RPC API for GUI communication

**Tasks:**
1. Create `orchestrator/api_server.py`:
   ```python
   class OrchestratorAPI:
       async def start_task(self, task: str, config: dict) -> str:
           """Start new orchestration run"""
       
       async def get_run_status(self, run_id: str) -> dict:
           """Get current status of a run"""
       
       async def pause_run(self, run_id: str) -> bool:
           """Pause active run"""
       
       async def resume_run(self, run_id: str) -> bool:
           """Resume paused run"""
       
       async def abort_run(self, run_id: str) -> bool:
           """Abort active run"""
       
       async def list_runs(self, filters: dict) -> List[dict]:
           """List runs with filters"""
       
       async def get_run_details(self, run_id: str) -> dict:
           """Get detailed run information"""
       
       async def get_live_logs(self, run_id: str) -> AsyncIterator[str]:
           """Stream live logs"""
       
       async def get_system_status(self) -> dict:
           """Get system health status"""
   ```

2. Add WebSocket support for live updates
3. Implement authentication (optional, for multi-user)
4. Add CORS headers for development

**Testing:**
- Unit tests for each API endpoint
- Integration tests with StateManager
- Load testing with concurrent requests

### Phase 2: Electron Setup (Week 3)

**Goal**: Bootstrap Electron application structure

**Tasks:**
1. Initialize Electron project:
   ```bash
   mkdir gui
   cd gui
   npm init -y
   npm install electron electron-builder
   ```

2. Create main process (`gui/src/main/main.ts`):
   - Window management
   - Python process spawning
   - IPC handlers

3. Create preload script (`gui/src/main/preload.ts`):
   - Expose safe IPC methods to renderer
   - Context isolation

4. Configure build scripts in `package.json`

**Testing:**
- Test Python process lifecycle
- Test IPC communication
- Test on all target platforms

### Phase 3: React Application (Week 4-5)

**Goal**: Build React UI components

**Tasks:**
1. Setup React with TypeScript:
   ```bash
   npx create-react-app gui-app --template typescript
   ```

2. Install dependencies:
   ```bash
   npm install @mui/material @emotion/react @emotion/styled
   npm install recharts react-router-dom
   npm install axios socket.io-client
   ```

3. Create component structure:
   ```
   gui/src/renderer/
   ├── components/
   │   ├── Dashboard/
   │   ├── RunMonitor/
   │   ├── History/
   │   ├── Settings/
   │   └── common/
   ├── contexts/
   │   ├── OrchestratorContext.tsx
   │   └── ThemeContext.tsx
   ├── hooks/
   │   ├── useOrchestrator.ts
   │   └── useWebSocket.ts
   ├── services/
   │   └── api.ts
   └── App.tsx
   ```

4. Implement components (see layouts above)

**Testing:**
- Component unit tests with React Testing Library
- Integration tests with mock API
- E2E tests with Playwright

### Phase 4: Integration (Week 6)

**Goal**: Connect frontend to backend

**Tasks:**
1. Implement API client service
2. Setup WebSocket for live updates
3. Add error handling and retry logic
4. Implement state synchronization
5. Add loading states and spinners

**Testing:**
- Test with real Python backend
- Test error scenarios
- Test reconnection logic

### Phase 5: Polish and Distribution (Week 7-8)

**Goal**: Prepare for release

**Tasks:**
1. Add keyboard shortcuts
2. Implement dark/light themes
3. Add accessibility features (ARIA labels, keyboard nav)
4. Create application icon and assets
5. Setup auto-updater
6. Write GUI documentation
7. Create installers for each platform

**Testing:**
- Accessibility audit
- Cross-platform testing
- User acceptance testing

## Technical Details

### Backend API Server

**File:** `orchestrator/api_server.py`

```python
from aiohttp import web
import socketio
from orchestrator import StateManager, ConfigLoader
import asyncio
import logging

logger = logging.getLogger(__name__)

class OrchestratorAPIServer:
    def __init__(self, host="127.0.0.1", port=8765):
        self.host = host
        self.port = port
        self.app = web.Application()
        self.sio = socketio.AsyncServer(async_mode='aiohttp', cors_allowed_origins='*')
        self.sio.attach(self.app)
        self.state_manager = None
        self.config = None
        self.active_runs = {}
        
        self._setup_routes()
        self._setup_socketio()
    
    def _setup_routes(self):
        self.app.router.add_post('/api/task/start', self.start_task)
        self.app.router.add_get('/api/run/{run_id}', self.get_run)
        self.app.router.add_post('/api/run/{run_id}/pause', self.pause_run)
        self.app.router.add_post('/api/run/{run_id}/resume', self.resume_run)
        self.app.router.add_post('/api/run/{run_id}/abort', self.abort_run)
        self.app.router.add_get('/api/runs', self.list_runs)
        self.app.router.add_get('/api/status', self.system_status)
    
    def _setup_socketio(self):
        @self.sio.event
        async def connect(sid, environ):
            logger.info(f"Client connected: {sid}")
        
        @self.sio.event
        async def disconnect(sid):
            logger.info(f"Client disconnected: {sid}")
        
        @self.sio.event
        async def subscribe_run(sid, run_id):
            await self.sio.enter_room(sid, f"run:{run_id}")
            logger.info(f"Client {sid} subscribed to run {run_id}")
    
    async def start_task(self, request):
        data = await request.json()
        task = data.get('task')
        config_overrides = data.get('config', {})
        
        # Start orchestration in background
        run_id = await self._execute_task(task, config_overrides)
        
        return web.json_response({'run_id': run_id})
    
    async def _execute_task(self, task: str, config_overrides: dict) -> str:
        # This would call the main orchestration logic
        # Send progress updates via WebSocket
        pass
    
    async def emit_progress(self, run_id: str, data: dict):
        await self.sio.emit('progress', data, room=f"run:{run_id}")
    
    async def start(self):
        self.state_manager = await StateManager.create()
        self.config = ConfigLoader.load_config()
        runner = web.AppRunner(self.app)
        await runner.setup()
        site = web.TCPSite(runner, self.host, self.port)
        await site.start()
        logger.info(f"API server started on {self.host}:{self.port}")

if __name__ == '__main__':
    server = OrchestratorAPIServer()
    asyncio.run(server.start())
```

### Electron Main Process

**File:** `gui/src/main/main.ts`

```typescript
import { app, BrowserWindow, ipcMain } from 'electron';
import { spawn, ChildProcess } from 'child_process';
import path from 'path';

let mainWindow: BrowserWindow | null = null;
let pythonProcess: ChildProcess | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.loadFile('index.html');
}

function startPythonBackend() {
  const pythonPath = process.platform === 'win32' ? 'python' : 'python3';
  const scriptPath = path.join(__dirname, '../../orchestrator/api_server.py');
  
  pythonProcess = spawn(pythonPath, [scriptPath]);
  
  pythonProcess.stdout?.on('data', (data) => {
    console.log(`Python: ${data}`);
  });
  
  pythonProcess.stderr?.on('data', (data) => {
    console.error(`Python Error: ${data}`);
  });
  
  pythonProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
  });
}

function stopPythonBackend() {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
}

app.whenReady().then(() => {
  startPythonBackend();
  createWindow();
});

app.on('window-all-closed', () => {
  stopPythonBackend();
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

ipcMain.handle('start-task', async (event, task: string) => {
  // Forward to Python API
});
```

### React Context

**File:** `gui/src/renderer/contexts/OrchestratorContext.tsx`

```typescript
import React, { createContext, useContext, useState, useEffect } from 'react';
import io from 'socket.io-client';
import { api } from '../services/api';

interface Run {
  id: string;
  task: string;
  status: string;
  progress: number;
}

interface OrchestratorContextType {
  runs: Run[];
  activeRun: Run | null;
  startTask: (task: string) => Promise<string>;
  pauseRun: (runId: string) => Promise<void>;
  resumeRun: (runId: string) => Promise<void>;
  abortRun: (runId: string) => Promise<void>;
}

const OrchestratorContext = createContext<OrchestratorContextType | null>(null);

export function OrchestratorProvider({ children }: { children: React.ReactNode }) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [activeRun, setActiveRun] = useState<Run | null>(null);
  const [socket, setSocket] = useState<any>(null);

  useEffect(() => {
    const newSocket = io('http://localhost:8765');
    setSocket(newSocket);

    newSocket.on('progress', (data: any) => {
      // Update run progress
      setRuns(prev => prev.map(run => 
        run.id === data.run_id ? { ...run, ...data } : run
      ));
    });

    return () => {
      newSocket.close();
    };
  }, []);

  const startTask = async (task: string): Promise<string> => {
    const response = await api.post('/api/task/start', { task });
    const runId = response.data.run_id;
    
    // Subscribe to updates
    socket.emit('subscribe_run', runId);
    
    return runId;
  };

  const pauseRun = async (runId: string) => {
    await api.post(`/api/run/${runId}/pause`);
  };

  const resumeRun = async (runId: string) => {
    await api.post(`/api/run/${runId}/resume`);
  };

  const abortRun = async (runId: string) => {
    await api.post(`/api/run/${runId}/abort`);
  };

  return (
    <OrchestratorContext.Provider value={{ runs, activeRun, startTask, pauseRun, resumeRun, abortRun }}>
      {children}
    </OrchestratorContext.Provider>
  );
}

export function useOrchestrator() {
  const context = useContext(OrchestratorContext);
  if (!context) {
    throw new Error('useOrchestrator must be used within OrchestratorProvider');
  }
  return context;
}
```

## Deployment

### Building Installers

**macOS:**
```bash
npm run build
npm run dist:mac
```

**Windows:**
```bash
npm run build
npm run dist:win
```

**Linux:**
```bash
npm run build
npm run dist:linux
```

### Distribution

1. **Code signing**: Sign binaries for each platform
2. **Notarization**: Notarize macOS app with Apple
3. **Auto-updates**: Setup update server or use GitHub releases
4. **Release notes**: Generate changelog for each version

## Best Practices

1. **Security**: Never expose sensitive data to renderer process
2. **Performance**: Use virtualization for long lists
3. **Responsiveness**: Show loading states for all async operations
4. **Error Handling**: Display user-friendly error messages
5. **Offline Support**: Handle API disconnections gracefully
6. **Testing**: Write tests for all critical paths
7. **Accessibility**: Follow WCAG guidelines
8. **Documentation**: Provide in-app help and tooltips

## Future Enhancements

1. **Plugins**: Allow users to add custom UI components
2. **Themes**: Support custom color schemes
3. **Workspaces**: Manage multiple projects
4. **Collaboration**: Real-time multi-user support
5. **Analytics**: Built-in metrics and insights
6. **Templates**: Task templates for common workflows
7. **Extensions**: Marketplace for community extensions

## References

- [Electron Documentation](https://www.electronjs.org/docs)
- [React Documentation](https://react.dev/)
- [Material-UI Components](https://mui.com/)
- [Socket.IO Documentation](https://socket.io/)
- [User Guide](USER_GUIDE.md)
- [Architecture](ARCHITECTURE.md)
