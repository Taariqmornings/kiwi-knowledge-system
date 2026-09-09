# Contributing to Kiwi

Welcome! We are excited that you are interested in contributing to **Kiwi - Offline Knowledge OS**. Kiwi is built and maintained by **Taariq Ebrahim** ([@Taariqmornings](https://github.com/Taariqmornings)), founder of Chatterbolic Solutions. The codebase is held to the same rigorous standards as production AI software.

By contributing to this repository, you help make offline information search and local AI RAG systems faster, more accessible, and highly reliable.

---

## 🛠️ Getting Started

### 📋 Prerequisites
Before you begin, ensure you have the following installed on your machine:
- **Node.js** (v20.19 or higher) & **npm** (v10 or higher)
- **Python** (v3.10 or higher)
- **Ollama** (locally installed and running: `ollama serve`)
  - Pull the default model: `ollama pull gemma3:1b`
- **PowerShell** (for Windows launcher scripts)

### 💻 Development Environment Setup
We provide automated launching scripts that manage setting up Python virtual environments and node dependencies for you.

To clone the repository and start developing:

1. **Clone the Repository & Navigate to the Root**
   ```bash
   git clone https://github.com/Taariqmornings/kiwi-knowledge-system.git
   cd kiwi-knowledge-system
   ```

2. **Launch in Development Mode (Hot-Reload Enabled)**
   - **On Windows (PowerShell)**:
     ```powershell
     .\start.ps1 -Dev
     ```
   - **On Windows (CMD / Batch)**:
     ```cmd
     start.bat -Dev
     ```
   
   This script will:
   - Create a Python virtual environment (`backend/venv/`) if missing.
   - Install and update Python backend dependencies.
   - Install React/Electron frontend packages.
   - Launch the FastAPI uvicorn backend on port `8000` with hot-reload enabled.
   - Launch the Vite development server on port `5173` with Hot Module Replacement (HMR) enabled.
   - Launch the Electron app window pointed at the Vite dev server.

---

## 🧪 Testing Guidelines

We value automated test coverage. Make sure all tests pass before proposing changes.

### 🐍 Backend Tests (FastAPI / pytest)
Backend tests are located in `backend/tests/`.
To run tests manually:
1. Activate virtual environment:
   ```powershell
   .\backend\venv\Scripts\Activate.ps1
   ```
2. Run tests via pytest:
   ```bash
   cd backend
   pytest
   ```

### ⚛️ Frontend Tests (React / Vitest)
Frontend tests are located in `frontend/src/__tests__/` or `frontend/test/`.
To run frontend tests:
```bash
cd frontend
npm run test
```

---

## 📐 Coding Standards & Architecture

To maintain code readability and keep our application lightweight and high-performing, please follow these guidelines:

### 🐍 Python (Backend)
- **Code Style**: Follow PEP 8 guidelines. Use clear variable names and explicit types.
- **SQLAlchemy**: Use SQLAlchemy 2.0 2.0-style queries (e.g. `db.execute(select(...))`). Keep transactions small and release connections using FastAPI dependency injection (`get_db`).
- **Error Handling**: Use structured try-except blocks and clean API response formatting (`HTTPException`). Avoid raw `print` statements—use the standard logger instead.

### ⚛️ TypeScript & React (Frontend)
- **Code Style**: Use strict TypeScript types. Avoid using `any` type definitions.
- **Components**: Create modular, reusable functional components. Leverage the context pattern (`AppContext`) for global app states.
- **Styling**: Write modular, clean vanilla CSS in `index.css`. Keep UI transitions smooth and use the project's core theme colors (deep slate backgrounds, cyan `#0ea5e9` highlights).

---

## 🤝 Branching & Pull Requests

1. **Create a Feature Branch**
   - Use descriptive branch names: `feature/your-feature-name` or `bugfix/issue-description`.
2. **Commit Your Changes**
   - Write clean, semantic commit messages:
     - `feat: add offline search autocomplete`
     - `fix: resolve db busy-timeout issue in WAL mode`
     - `docs: update setup instructions in readme`
3. **Open a Pull Request**
   - Ensure your code passes frontend linting (`npm run lint`), backend tests, and typescript compilations.
   - Reference any related issues in the PR description.
