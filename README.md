# Virtual Memory Simulator

A web-based virtual memory management simulator built with React frontend and Flask backend. Demonstrates paging, page replacement algorithms, TLB operations, and working set analysis.

## Features
* Physical memory visualization with 16 frames
* Page table management for multiple processes
* Page replacement algorithms: FIFO, LRU, Clock, Optimal
* Translation Lookaside Buffer (TLB) simulation
* Working set analysis and thrashing detection
* Real-time address translation with step-by-step breakdown
* Algorithm performance comparison
* Comprehensive system reports

## Requirements
* Node.js and npm
* Python 3.x
* Flask and Flask-CORS

## Installation
1.  Clone or download the project
2.  Install Python dependencies:
    ```bash
    pip install flask flask-cors
    ```
3.  Install React dependencies:
    ```bash
    cd frontend
    npm install
    ```

## Running the Application
You need to run both frontend and backend simultaneously in separate terminals.

### Terminal 1 - Backend
```bash
cd backend
python app.py

### Terminal 2 - Frontend
```bash
cd frontend
npx react-scripts start