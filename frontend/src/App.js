import React, { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';
import { 
  Play, Square, RotateCcw, Plus, Minus, 
  Monitor, Database, Activity, Settings,
  AlertCircle, CheckCircle, Search, BarChart3,
  FileText, Shuffle, TrendingUp, Cpu,
  Clock, Target, Layers, Zap
} from 'lucide-react';
import './App.css';

const API_BASE = process.env.NODE_ENV === 'production' 
  ? '/api' 
  : 'http://localhost:5001/api';

function App() {
  const [memoryState, setMemoryState] = useState(null);
  const [currentAlgorithm, setCurrentAlgorithm] = useState('FIFO');
  const [newProcessPages, setNewProcessPages] = useState(4);
  const [selectedProcess, setSelectedProcess] = useState('');
  const [virtualAddress, setVirtualAddress] = useState('');
  const [translationResult, setTranslationResult] = useState(null);
  const [isRunning, setIsRunning] = useState(false);
  const [demoResults, setDemoResults] = useState([]);
  const [connectionStatus, setConnectionStatus] = useState('connecting');
  const [error, setError] = useState(null);
  const [algorithmComparison, setAlgorithmComparison] = useState(null);
  const [report, setReport] = useState(null);
  const [workingSets, setWorkingSets] = useState(null);
  const [tlbState, setTlbState] = useState(null);
  const [showComparison, setShowComparison] = useState(false);
  const [showReport, setShowReport] = useState(false);
  const [showTlb, setShowTlb] = useState(false);
  const [showWorkingSets, setShowWorkingSets] = useState(false);
  const [randomAccessCount, setRandomAccessCount] = useState(10);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [startTime, setStartTime] = useState(new Date());
  const [lastAccessTime, setLastAccessTime] = useState(null);
  const [showRealTimeMonitor, setShowRealTimeMonitor] = useState(false);
  const [benchmarkResults, setBenchmarkResults] = useState(null);
  const [showBenchmark, setShowBenchmark] = useState(false);
  const [isBenchmarkRunning, setIsBenchmarkRunning] = useState(false);
  const [systemResources, setSystemResources] = useState({
    frameUtilization: 0,
    tlbUtilization: 0,
    algorithmEfficiency: 0
  });
  const [showSystemResources, setShowSystemResources] = useState(false);

  const cursorDotRef = useRef(null);
  const cursorOutlineRef = useRef(null);
  const requestRef = useRef();
  const mousePosition = useRef({ x: 0, y: 0 });
  const cursorPosition = useRef({ x: 0, y: 0 });
  const demoIntervalRef = useRef(null);

  const calculateSystemResources = useCallback(() => {
    if (!memoryState) return;

    const totalFrames = memoryState.physical_memory?.length || 16;
    const usedFrames = memoryState.physical_memory?.filter(frame => frame !== null).length || 0;
    const frameUtilization = (usedFrames / totalFrames) * 100;

    const tlbSize = 4;
    const tlbEntries = Object.keys(tlbState?.tlb || {}).length;
    const tlbUtilization = (tlbEntries / tlbSize) * 100;

    const stats = memoryState.stats || {};
    const algorithmEfficiency = stats.hit_ratio ? stats.hit_ratio * 100 : 0;

    setSystemResources({
      frameUtilization: frameUtilization.toFixed(1),
      tlbUtilization: tlbUtilization.toFixed(1),
      algorithmEfficiency: algorithmEfficiency.toFixed(1)
    });
  }, [memoryState, tlbState]);

  useEffect(() => {
    checkConnection();
    initializeCursor();
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => {
      if (requestRef.current) {
        cancelAnimationFrame(requestRef.current);
      }
      clearInterval(timer);
      if (demoIntervalRef.current) {
        clearInterval(demoIntervalRef.current);
      }
    };
  }, []);

  useEffect(() => {
    calculateSystemResources();
  }, [calculateSystemResources]);

  const formatUptime = (startTime, currentTime) => {
    const diffInSeconds = Math.floor((currentTime - startTime) / 1000);
    const hours = Math.floor(diffInSeconds / 3600);
    const minutes = Math.floor((diffInSeconds % 3600) / 60);
    const seconds = diffInSeconds % 60;
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
  };

  const stopDemo = () => {
    setIsRunning(false);
    if (demoIntervalRef.current) {
      clearInterval(demoIntervalRef.current);
      demoIntervalRef.current = null;
    }
  };

  const runBenchmark = async () => {
    if (connectionStatus !== 'connected') {
      setError('Not connected to backend');
      return;
    }

    setIsBenchmarkRunning(true);
    setBenchmarkResults(null);

    try {
      const benchmarkSequences = {
        sequential: [],
        random: [],
        locality: []
      };

      for (let i = 0; i < 20; i++) {
        benchmarkSequences.sequential.push([1, i * 0x1000]);
      }

      for (let i = 0; i < 20; i++) {
        benchmarkSequences.random.push([1, Math.floor(Math.random() * 0x10000)]);
      }

      const localityBase = [0x1000, 0x2000, 0x3000];
      for (let i = 0; i < 20; i++) {
        const base = localityBase[i % 3];
        benchmarkSequences.locality.push([1, base + (Math.random() < 0.8 ? 0 : 0x1000)]);
      }

      const results = {};
      const algorithms = ['FIFO', 'LRU', 'Clock'];

      for (const pattern of Object.keys(benchmarkSequences)) {
        results[pattern] = {};
        
        for (const algorithm of algorithms) {
          try {
            await axios.post(`${API_BASE}/reset`);
            await axios.post(`${API_BASE}/create_process`, { pages: 8 });
            await axios.post(`${API_BASE}/set_algorithm`, { algorithm });

            const startTime = performance.now();
            
            for (const [pid, addr] of benchmarkSequences[pattern]) {
              await axios.post(`${API_BASE}/translate_address`, {
                pid: parseInt(pid),
                virtual_address: parseInt(addr)
              });
            }

            const endTime = performance.now();
            const memState = await axios.get(`${API_BASE}/memory_state`);
            
            results[pattern][algorithm] = {
              page_faults: memState.data.stats.page_faults,
              hit_ratio: memState.data.stats.hit_ratio,
              execution_time: endTime - startTime
            };
          } catch (error) {
            results[pattern][algorithm] = {
              page_faults: 0,
              hit_ratio: 0,
              execution_time: 0,
              error: error.message
            };
          }
        }
      }

      setBenchmarkResults(results);
      setShowBenchmark(true);
    } catch (error) {
      setError('Benchmark failed: ' + error.message);
    }

    setIsBenchmarkRunning(false);
  };

  const initializeCursor = () => {
    const cursorDot = document.createElement('div');
    cursorDot.id = 'cursor-dot';
    document.body.appendChild(cursorDot);

    const cursorOutline = document.createElement('div');
    cursorOutline.id = 'cursor-dot-outline';
    document.body.appendChild(cursorOutline);

    cursorDotRef.current = cursorDot;
    cursorOutlineRef.current = cursorOutline;

    const handleMouseMove = (e) => {
      mousePosition.current = { x: e.clientX, y: e.clientY };
      if (cursorDotRef.current && cursorOutlineRef.current) {
        cursorDotRef.current.style.opacity = '1';
        cursorOutlineRef.current.style.opacity = '1';
      }
    };

    const handleMouseLeave = () => {
      if (cursorDotRef.current && cursorOutlineRef.current) {
        cursorDotRef.current.style.opacity = '0';
        cursorOutlineRef.current.style.opacity = '0';
      }
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseleave', handleMouseLeave);

    const animateCursor = () => {
      const { x: mouseX, y: mouseY } = mousePosition.current;
      const { x: cursorX, y: cursorY } = cursorPosition.current;

      const dx = mouseX - cursorX;
      const dy = mouseY - cursorY;

      cursorPosition.current = {
        x: cursorX + dx * 0.1,
        y: cursorY + dy * 0.1
      };

      if (cursorDotRef.current) {
        cursorDotRef.current.style.left = `${mouseX}px`;
        cursorDotRef.current.style.top = `${mouseY}px`;
      }

      if (cursorOutlineRef.current) {
        cursorOutlineRef.current.style.left = `${cursorPosition.current.x}px`;
        cursorOutlineRef.current.style.top = `${cursorPosition.current.y}px`;
      }

      requestRef.current = requestAnimationFrame(animateCursor);
    };

    animateCursor();

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseleave', handleMouseLeave);
      if (cursorDotRef.current && document.body.contains(cursorDotRef.current)) {
        document.body.removeChild(cursorDotRef.current);
      }
      if (cursorOutlineRef.current && document.body.contains(cursorOutlineRef.current)) {
        document.body.removeChild(cursorOutlineRef.current);
      }
    };
  };

  useEffect(() => {
    const createParticles = () => {
      const particlesContainer = document.createElement('div');
      particlesContainer.className = 'floating-particles';
      
      for (let i = 0; i < 9; i++) {
        const particle = document.createElement('div');
        particle.className = 'particle';
        particlesContainer.appendChild(particle);
      }
      
      document.body.appendChild(particlesContainer);
      
      return () => {
        if (document.body.contains(particlesContainer)) {
          document.body.removeChild(particlesContainer);
        }
      };
    };
    
    const cleanupParticles = createParticles();
    
    return cleanupParticles;
  }, []);

  const checkConnection = async () => {
    try {
      setConnectionStatus('connecting');
      const response = await axios.get(`${API_BASE}/memory_state`, { 
        timeout: 5000
      });
      setMemoryState(response.data);
      setConnectionStatus('connected');
      setError(null);
      setStartTime(new Date());
    } catch (error) {
      setConnectionStatus('disconnected');
      setError('Cannot connect to backend. Make sure Flask server is running on port 5001.');
    }
  };

  const createProcess = async () => {
    if (connectionStatus !== 'connected') {
      setError('Not connected to backend');
      return;
    }

    try {
      const response = await axios.post(`${API_BASE}/create_process`, {
        pages: parseInt(newProcessPages)
      });
      
      if (response.data.success) {
        setMemoryState(response.data.memory_state);
        setError(null);
        fetchWorkingSets();
      } else {
        setError('Failed to create process');
      }
    } catch (error) {
      setError('Error creating process: ' + error.message);
    }
  };

  const terminateProcess = async (pid) => {
    if (connectionStatus !== 'connected') {
      setError('Not connected to backend');
      return;
    }

    try {
      const response = await axios.post(`${API_BASE}/terminate_process`, {
        pid: parseInt(pid)
      });
      
      if (response.data.success) {
        setMemoryState(response.data.memory_state);
        setError(null);
        fetchWorkingSets();
      } else {
        setError('Failed to terminate process');
      }
    } catch (error) {
      setError('Error terminating process: ' + error.message);
    }
  };

  const translateAddress = async () => {
    if (!selectedProcess || !virtualAddress) {
      setError('Please select a process and enter a virtual address');
      return;
    }
    
    if (connectionStatus !== 'connected') {
      setError('Not connected to backend');
      return;
    }

    try {
      const response = await axios.post(`${API_BASE}/translate_address`, {
        pid: parseInt(selectedProcess),
        virtual_address: parseInt(virtualAddress, 16)
      });
      
      setTranslationResult(response.data.result);
      setMemoryState(response.data.memory_state);
      setError(null);
      setLastAccessTime(new Date());
      fetchTlbState();
      fetchWorkingSets();
    } catch (error) {
      setError('Error translating address: ' + error.message);
    }
  };

  const changeAlgorithm = async (algorithm) => {
    if (connectionStatus !== 'connected') {
      setError('Not connected to backend');
      return;
    }

    try {
      const response = await axios.post(`${API_BASE}/set_algorithm`, {
        algorithm
      });
      
      if (response.data.success) {
        setCurrentAlgorithm(algorithm);
        setMemoryState(response.data.memory_state);
        setError(null);
      }
    } catch (error) {
      setError('Error changing algorithm: ' + error.message);
    }
  };

  const resetSimulator = async () => {
    if (connectionStatus !== 'connected') {
      setError('Not connected to backend');
      return;
    }

    try {
      const response = await axios.post(`${API_BASE}/reset`);
      
      if (response.data.success) {
        setMemoryState(response.data.memory_state);
        setTranslationResult(null);
        setDemoResults([]);
        setCurrentAlgorithm('FIFO');
        setSelectedProcess('');
        setVirtualAddress('');
        setAlgorithmComparison(null);
        setReport(null);
        setWorkingSets(null);
        setTlbState(null);
        setShowComparison(false);
        setShowReport(false);
        setShowTlb(false);
        setShowWorkingSets(false);
        setShowRealTimeMonitor(false);
        setShowBenchmark(false);
        setShowSystemResources(false);
        setBenchmarkResults(null);
        setLastAccessTime(null);
        setStartTime(new Date());
        setError(null);
        if (demoIntervalRef.current) {
          clearInterval(demoIntervalRef.current);
          demoIntervalRef.current = null;
        }
        setIsRunning(false);
      }
    } catch (error) {
      setError('Error resetting simulator: ' + error.message);
    }
  };

  const runDemo = async () => {
    if (connectionStatus !== 'connected') {
      setError('Not connected to backend');
      return;
    }

    setIsRunning(true);
    try {
      const response = await axios.post(`${API_BASE}/run_demo`);
      
      if (response.data.success) {
        setMemoryState(response.data.memory_state);
        setDemoResults(response.data.demo_results || []);
        setError(null);
        setLastAccessTime(new Date());
        fetchTlbState();
        fetchWorkingSets();
      } else {
        setError('Demo failed to run');
      }
    } catch (error) {
      setError('Error running demo: ' + error.message);
    }
    setIsRunning(false);
  };

  const compareAlgorithms = async () => {
    if (connectionStatus !== 'connected') {
      setError('Not connected to backend');
      return;
    }
    
    try {
      const testSequences = [
        [1, 0x0000], [1, 0x1000], [1, 0x2000], [2, 0x0000], [2, 0x1000],
        [1, 0x3000], [1, 0x4000], [1, 0x5000], [2, 0x2000], [2, 0x3000],
        [1, 0x0000], [1, 0x1000], [1, 0x6000], [1, 0x7000], [2, 0x0000]
      ];

      const response = await axios.post(`${API_BASE}/compare_algorithms`, {
        sequences: testSequences,
        future_accesses: testSequences.slice(5)
      });
      
      if (response.data.success) {
        setAlgorithmComparison(response.data.comparison);
        setShowComparison(true);
        setError(null);
      } else {
        setError('Algorithm comparison failed: ' + (response.data.error || 'Unknown error'));
      }
    } catch (error) {
      setError('Error comparing algorithms: ' + error.message);
    }
  };

  const generateReport = async () => {
    if (connectionStatus !== 'connected') {
      setError('Not connected to backend');
      return;
    }

    try {
      const response = await axios.get(`${API_BASE}/generate_report`);
      
      if (response.data.success) {
        setReport(response.data.report);
        setShowReport(true);
        setError(null);
      }
    } catch (error) {
      setError('Error generating report: ' + error.message);
    }
  };

  const fetchWorkingSets = async () => {
    if (connectionStatus !== 'connected') return;

    try {
      const response = await axios.get(`${API_BASE}/working_sets`);
      if (response.data.success) {
        setWorkingSets(response.data.working_sets);
      }
    } catch (error) {
      console.error('Error fetching working sets:', error);
    }
  };

  const fetchTlbState = async () => {
    if (connectionStatus !== 'connected') return;

    try {
      const response = await axios.get(`${API_BASE}/tlb_state`);
      if (response.data.success) {
        setTlbState(response.data);
      }
    } catch (error) {
      console.error('Error fetching TLB state:', error);
    }
  };

  const runRandomAccess = async () => {
    if (connectionStatus !== 'connected') {
      setError('Not connected to backend');
      return;
    }

    try {
      const response = await axios.post(`${API_BASE}/random_access`, {
        count: parseInt(randomAccessCount)
      });
      
      if (response.data.success) {
        setMemoryState(response.data.memory_state);
        setDemoResults(response.data.results);
        setLastAccessTime(new Date());
        setError(null);
        fetchTlbState();
        fetchWorkingSets();
      }
    } catch (error) {
      setError('Error running random access: ' + error.message);
    }
  };

  const renderConnectionStatus = () => {
    return (
      <div className={`connection-status ${connectionStatus}`}>
        {connectionStatus === 'connected' && (
          <>
            <CheckCircle size={16} />
            <span>Connected</span>
          </>
        )}
        {connectionStatus === 'connecting' && (
          <>
            <div className="spinner"></div>
            <span>Connecting...</span>
          </>
        )}
        {connectionStatus === 'disconnected' && (
          <>
            <AlertCircle size={16} />
            <span>Disconnected</span>
            <button onClick={checkConnection} className="retry-btn">Retry</button>
          </>
        )}
      </div>
    );
  };

  const renderError = () => {
    if (!error) return null;
    
    return (
      <div className="error-message">
        <AlertCircle size={16} />
        <span>{error}</span>
        <button onClick={() => setError(null)} className="close-error">×</button>
      </div>
    );
  };

  const renderPhysicalMemory = () => {
    if (!memoryState) {
      return (
        <div className="loading-state">
          <p>Connecting to backend...</p>
          <button onClick={checkConnection} className="retry-btn">Try Again</button>
        </div>
      );
    }
    
    return (
      <div className="memory-grid">
        {(memoryState.physical_memory || []).map((frame, index) => (
          <div 
            key={index}
            className={`memory-frame ${frame ? 'occupied' : 'free'}`}
            style={{
              backgroundColor: frame 
                ? `hsl(${(frame.pid * 60) % 360}, 70%, 85%)`
                : '#fce7f3'
            }}
          >
            <div className="frame-number">Frame {index}</div>
            {frame && (
              <div className="frame-content">
                <div>PID: {frame.pid}</div>
                <div>Page: {frame.page}</div>
              </div>
            )}
          </div>
        ))}
      </div>
    );
  };

  const renderPageTables = () => {
    if (!memoryState || !memoryState.processes || Object.keys(memoryState.processes).length === 0) {
      return (
        <div className="loading-state">
          <p>No processes created yet. Click "Create Process" to start!</p>
        </div>
      );
    }
    
    return Object.entries(memoryState.processes).map(([pid, process]) => (
      <div key={pid} className="page-table">
        <h3>Process {pid} Page Table 
          {workingSets && workingSets[pid] && (
            <span className="working-set-info">
              (Working Set: {workingSets[pid].size} pages)
            </span>
          )}
        </h3>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Page</th>
                <th>Frame</th>
                <th>Valid</th>
                <th>Dirty</th>
                <th>Referenced</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(process.page_table || {}).map(([pageNum, pageEntry]) => (
                <tr key={pageNum} className={`${pageEntry.valid ? 'valid-page' : 'invalid-page'} ${
                  workingSets && workingSets[pid] && workingSets[pid].current_set.includes(parseInt(pageNum)) ? 'working-set-page' : ''
                }`}>
                  <td>{pageNum}</td>
                  <td>{pageEntry.frame !== null ? pageEntry.frame : '-'}</td>
                  <td>{pageEntry.valid ? '✓' : '✗'}</td>
                  <td>{pageEntry.dirty ? '✓' : '✗'}</td>
                  <td>{pageEntry.referenced ? '✓' : '✗'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    ));
  };

  const renderTranslationSteps = () => {
    if (!translationResult || !translationResult.translation_steps) return null;

    return (
      <div className="translation-steps">
        <h4>Translation Steps:</h4>
        <div className="steps-list">
          {translationResult.translation_steps.map((step, index) => (
            <div key={index} className={`step-item step-${step.step}`}>
              <div className="step-number">{index + 1}</div>
              <div className="step-description">{step.description}</div>
            </div>
          ))}
        </div>
      </div>
    );
  };

  const renderStats = () => {
    if (!memoryState || !memoryState.stats) {
      return (
        <div className="stats-panel">
          <h3>Performance Statistics</h3>
          <div className="loading-state">
            <p>Waiting for connection...</p>
          </div>
        </div>
      );
    }
    
    const stats = memoryState.stats;
    
    return (
      <div className="stats-panel">
        <h3>Performance Statistics</h3>
        <div className="stats-grid">
          <div className="stat-item">
            <div className="stat-label">Memory Accesses</div>
            <div className="stat-value">{stats.memory_accesses}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">Page Faults</div>
            <div className="stat-value">{stats.page_faults}</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">Hit Ratio</div>
            <div className="stat-value">{(stats.hit_ratio * 100).toFixed(2)}%</div>
          </div>
          <div className="stat-item">
            <div className="stat-label">Algorithm</div>
            <div className="stat-value">{memoryState.current_algorithm}</div>
          </div>
          {tlbState && tlbState.stats && (
            <div className="stat-item">
              <div className="stat-label">TLB Hit Ratio</div>
              <div className="stat-value">{(tlbState.stats.hit_ratio * 100).toFixed(2)}%</div>
            </div>
          )}
          {stats.thrashing_detected && (
            <div className="stat-item warning">
              <div className="stat-label">Thrashing</div>
              <div className="stat-value">Detected!</div>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="App">
      <header className="app-header">
        <h1><Monitor className="header-icon" /> Virtual Memory Simulator</h1>
        <div className="header-controls">
          {renderConnectionStatus()}
          <button 
            onClick={runDemo} 
            disabled={isRunning || connectionStatus !== 'connected'} 
            className="demo-btn"
          >
            <Play size={16} /> {isRunning ? 'Running...' : 'Run Demo'}
          </button>
          <button 
            onClick={stopDemo} 
            disabled={!isRunning || connectionStatus !== 'connected'} 
            className="stop-btn"
          >
            <Square size={16} /> Stop Demo
          </button>
          <button 
            onClick={resetSimulator} 
            disabled={connectionStatus !== 'connected'} 
            className="reset-btn"
          >
            <RotateCcw size={16} /> Reset
          </button>
        </div>
      </header>

      {renderError()}

      <div className="main-container">
        <div className="left-panel">
          <div className="control-section">
            <h3><Settings size={20} /> Algorithm Selection</h3>
            <div className="algorithm-buttons">
              {['FIFO', 'LRU', 'Clock', 'Optimal'].map(algo => (
                <button
                  key={algo}
                  onClick={() => changeAlgorithm(algo)}
                  disabled={connectionStatus !== 'connected'}
                  className={`algo-btn ${currentAlgorithm === algo ? 'active' : ''}`}
                >
                  {algo}
                </button>
              ))}
            </div>
          </div>

          <div className="control-section">
            <h3><Plus size={20} /> Process Management</h3>
            <div className="process-controls">
              <label>
                Pages needed:
                <input
                  type="number"
                  value={newProcessPages}
                  onChange={(e) => setNewProcessPages(e.target.value)}
                  min="1"
                  max="16"
                  disabled={connectionStatus !== 'connected'}
                />
              </label>
              <button 
                onClick={createProcess} 
                disabled={connectionStatus !== 'connected'}
                className="create-btn"
              >
                <Plus size={16} /> Create Process
              </button>
            </div>

            {memoryState && memoryState.processes && Object.keys(memoryState.processes).length > 0 && (
              <div className="process-list">
                <h4>Active Processes:</h4>
                {Object.entries(memoryState.processes).map(([pid, process]) => (
                  <div key={pid} className="process-item">
                    <span>PID {pid} ({process.allocated_pages}/{process.pages_needed} pages)
                      {process.working_set_size > 0 && ` WS: ${process.working_set_size}`}
                    </span>
                    <button 
                      onClick={() => terminateProcess(pid)}
                      disabled={connectionStatus !== 'connected'}
                      className="terminate-btn"
                    >
                      <Minus size={14} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="control-section">
            <h3><Search size={20} /> Address Translation</h3>
            <div className="translation-controls">
              <label>
                Process ID:
                <select 
                  value={selectedProcess} 
                  onChange={(e) => setSelectedProcess(e.target.value)}
                  disabled={connectionStatus !== 'connected'}
                >
                  <option value="">Select Process</option>
                  {memoryState && memoryState.processes && Object.keys(memoryState.processes).map(pid => (
                    <option key={pid} value={pid}>Process {pid}</option>
                  ))}
                </select>
              </label>
              <label>
                Virtual Address (hex):
                <input
                  type="text"
                  value={virtualAddress}
                  onChange={(e) => setVirtualAddress(e.target.value)}
                 placeholder="e.g., 1000"
                 disabled={connectionStatus !== 'connected'}
               />
             </label>
             <button 
               onClick={translateAddress} 
               disabled={connectionStatus !== 'connected'}
               className="translate-btn"
             >
               Translate Address
             </button>
           </div>
           
           {translationResult && (
             <div className="translation-result">
               <h4>Translation Result:</h4>
               <div>
                 <p>Physical Address: 0x{translationResult.physical_address.toString(16)}</p>
                 <p>Frame: {translationResult.frame}</p>
                 <p>Page Fault: {translationResult.page_fault ? 'Yes' : 'No'}</p>
                 <p>TLB Hit: {translationResult.tlb_hit ? 'Yes' : 'No'}</p>
                 {renderTranslationSteps()}
               </div>
             </div>
           )}
         </div>

         <div className="control-section">
           <h3><Clock size={20} /> Real-time Monitor</h3>
           <div className="realtime-controls">
             <button 
               onClick={() => setShowRealTimeMonitor(!showRealTimeMonitor)} 
               disabled={connectionStatus !== 'connected'}
               className={`analysis-btn ${showRealTimeMonitor ? 'active' : ''}`}
             >
               <Clock size={16} /> {showRealTimeMonitor ? 'Hide Monitor' : 'Show Monitor'}
             </button>
           </div>
           
           {showRealTimeMonitor && (
             <div className="realtime-stats">
               <div className="realtime-item">
                 <span className="realtime-label">Current Time:</span>
                 <span className="realtime-value">{currentTime.toLocaleTimeString()}</span>
               </div>
               <div className="realtime-item">
                 <span className="realtime-label">Uptime:</span>
                 <span className="realtime-value">{formatUptime(startTime, currentTime)}</span>
               </div>
               <div className="realtime-item">
                 <span className="realtime-label">Last Access:</span>
                 <span className="realtime-value">
                   {lastAccessTime ? lastAccessTime.toLocaleTimeString() : 'None'}
                 </span>
               </div>
             </div>
           )}
         </div>

         <div className="control-section">
           <h3><Cpu size={20} /> System Resources</h3>
           <div className="resource-controls">
             <button 
               onClick={() => setShowSystemResources(!showSystemResources)} 
               disabled={connectionStatus !== 'connected'}
               className={`analysis-btn ${showSystemResources ? 'active' : ''}`}
             >
               <Cpu size={16} /> {showSystemResources ? 'Hide Resources' : 'Show Resources'}
             </button>
           </div>
           
           {showSystemResources && (
             <div className="resource-stats">
               <div className="resource-item">
                 <span className="resource-label">Frame Utilization:</span>
                 <span className="resource-value">{systemResources.frameUtilization}%</span>
               </div>
               <div className="resource-item">
                 <span className="resource-label">TLB Utilization:</span>
                 <span className="resource-value">{systemResources.tlbUtilization}%</span>
               </div>
               <div className="resource-item">
                 <span className="resource-label">Algorithm Efficiency:</span>
                 <span className="resource-value">{systemResources.algorithmEfficiency}%</span>
               </div>
             </div>
           )}
         </div>

         <div className="control-section">
           <h3><TrendingUp size={20} /> Analysis Tools</h3>
           <div className="analysis-buttons">
             <button 
               onClick={compareAlgorithms} 
               disabled={connectionStatus !== 'connected'}
               className="analysis-btn"
             >
               <BarChart3 size={16} /> Compare Algorithms
             </button>
             <button 
               onClick={generateReport} 
               disabled={connectionStatus !== 'connected'}
               className="analysis-btn"
             >
               <FileText size={16} /> Generate Report
             </button>
             <button 
               onClick={runBenchmark} 
               disabled={connectionStatus !== 'connected' || isBenchmarkRunning}
               className="analysis-btn"
             >
               <Target size={16} /> {isBenchmarkRunning ? 'Running...' : 'Run Benchmark'}
             </button>
             <button 
               onClick={() => {setShowTlb(!showTlb); if (!showTlb) fetchTlbState();}} 
               disabled={connectionStatus !== 'connected'}
               className={`analysis-btn ${showTlb ? 'active' : ''}`}
             >
               <Zap size={16} /> TLB State
             </button>
             <button 
               onClick={() => {setShowWorkingSets(!showWorkingSets); if (!showWorkingSets) fetchWorkingSets();}} 
               disabled={connectionStatus !== 'connected'}
               className={`analysis-btn ${showWorkingSets ? 'active' : ''}`}
             >
               <Layers size={16} /> Working Sets
             </button>
           </div>
           
           <div className="random-controls">
             <label>
               Random accesses:
               <input
                 type="number"
                 value={randomAccessCount}
                 onChange={(e) => setRandomAccessCount(e.target.value)}
                 min="1"
                 max="50"
                 disabled={connectionStatus !== 'connected'}
               />
             </label>
             <button 
               onClick={runRandomAccess} 
               disabled={connectionStatus !== 'connected'}
               className="random-btn"
             >
               <Shuffle size={16} /> Random Access
             </button>
           </div>
         </div>
         {renderStats()}
       </div>

       <div className="right-panel">
         <div className="memory-section">
           <h3><Monitor size={20} /> Physical Memory ({memoryState ? '16 frames' : 'Loading...'})</h3>
           {renderPhysicalMemory()}
         </div>

         <div className="page-tables-section">
           <h3><Database size={20} /> Page Tables</h3>
           <div className="page-tables-container">
             {renderPageTables()}
           </div>
         </div>

         {demoResults.length > 0 && (
           <div className="demo-section">
             <h3><Activity size={20} /> Access Results</h3>
             <div className="demo-results">
               {demoResults.slice(-10).map((result, index) => (
                 <div key={index} className="demo-item">
                   <p>
                     PID {result.pid}: 0x{result.virtual_address.toString(16)} → 
                     {result.result ? (
                       <>
                         Frame {result.result.frame}
                         {result.result.page_fault && <span className="fault-indicator"> [PAGE FAULT]</span>}
                         {result.result.tlb_hit && <span className="tlb-indicator"> [TLB HIT]</span>}
                       </>
                     ) : ' Failed'}
                   </p>
                 </div>
               ))}
             </div>
           </div>
         )}
       </div>
     </div>

     {showComparison && algorithmComparison && (
       <div className="comparison-modal">
         <div className="modal-content">
           <div className="modal-header">
             <h3><BarChart3 size={20} /> Algorithm Performance Comparison</h3>
             <button onClick={() => setShowComparison(false)} className="close-btn">×</button>
           </div>
           <div className="comparison-table">
             <table>
               <thead>
                 <tr>
                   <th>Algorithm</th>
                   <th>Page Faults</th>
                   <th>Memory Accesses</th>
                   <th>Fault Rate</th>
                   <th>Hit Rate</th>
                 </tr>
               </thead>
               <tbody>
                 {Object.entries(algorithmComparison).map(([algo, stats]) => (
                   <tr key={algo} className={algo === currentAlgorithm ? 'current-algorithm' : ''}>
                     <td>{algo}</td>
                     <td>{stats.page_faults}</td>
                     <td>{stats.accesses}</td>
                     <td>{(stats.fault_rate * 100).toFixed(2)}%</td>
                     <td>{(stats.hit_rate * 100).toFixed(2)}%</td>
                   </tr>
                 ))}
               </tbody>
             </table>
           </div>
         </div>
       </div>
     )}

     {showBenchmark && benchmarkResults && (
       <div className="comparison-modal">
         <div className="modal-content large-modal">
           <div className="modal-header">
             <h3><Target size={20} /> Benchmark Results</h3>
             <button onClick={() => setShowBenchmark(false)} className="close-btn">×</button>
           </div>
           <div className="benchmark-content">
             {Object.entries(benchmarkResults).map(([pattern, results]) => (
               <div key={pattern} className="benchmark-section">
                 <h4>{pattern.charAt(0).toUpperCase() + pattern.slice(1)} Access Pattern</h4>
                 <table>
                   <thead>
                     <tr>
                       <th>Algorithm</th>
                       <th>Page Faults</th>
                       <th>Hit Ratio</th>
                       <th>Execution Time (ms)</th>
                     </tr>
                   </thead>
                   <tbody>
                     {Object.entries(results).map(([algo, stats]) => (
                       <tr key={algo}>
                         <td>{algo}</td>
                         <td>{stats.page_faults}</td>
                         <td>{(stats.hit_ratio * 100).toFixed(2)}%</td>
                         <td>{stats.execution_time.toFixed(2)}</td>
                       </tr>
                     ))}
                   </tbody>
                 </table>
               </div>
             ))}
           </div>
         </div>
       </div>
     )}

     {showReport && report && (
       <div className="report-modal">
         <div className="modal-content large-modal">
           <div className="modal-header">
             <h3><FileText size={20} /> System Performance Report</h3>
             <button onClick={() => setShowReport(false)} className="close-btn">×</button>
           </div>
           <div className="report-content">
             {report.system_info && (
               <div className="report-section">
                 <h4>System Information</h4>
                 <div className="info-grid">
                   <div>Total Frames: {report.system_info.total_frames}</div>
                   <div>Used Frames: {report.system_info.used_frames}</div>
                   <div>Free Frames: {report.system_info.free_frames}</div>
                   <div>Page Size: {report.system_info.page_size} bytes</div>
                   <div>Current Algorithm: {report.system_info.current_algorithm}</div>
                 </div>
               </div>
             )}
             
             {report.performance_stats && (
               <div className="report-section">
                 <h4>Performance Statistics</h4>
                 <div className="stats-grid">
                   <div>Total Accesses: {report.performance_stats.total_accesses}</div>
                   <div>Page Faults: {report.performance_stats.page_faults}</div>
                   <div>Hit Ratio: {(report.performance_stats.hit_ratio * 100).toFixed(2)}%</div>
                   <div>TLB Hit Ratio: {(report.performance_stats.tlb_hit_ratio * 100).toFixed(2)}%</div>
                 </div>
               </div>
             )}

             {report.process_info && (
               <div className="report-section">
                 <h4>Process Information</h4>
                 <table>
                   <thead>
                     <tr>
                       <th>PID</th>
                       <th>Allocated Pages</th>
                       <th>Total Pages</th>
                       <th>Working Set Size</th>
                     </tr>
                   </thead>
                   <tbody>
                     {Object.entries(report.process_info).map(([pid, info]) => (
                       <tr key={pid}>
                         <td>{pid}</td>
                         <td>{info.pages_allocated}</td>
                         <td>{info.pages_needed}</td>
                         <td>{info.working_set_size}</td>
                       </tr>
                     ))}
                   </tbody>
                 </table>
               </div>
             )}

             {report.thrashing_detected && (
               <div className="report-section warning">
                 <h4>Thrashing Detected</h4>
                 <p>High page fault rate detected. Consider increasing memory or reducing process working sets.</p>
               </div>
             )}
           </div>
         </div>
       </div>
     )}

     {showTlb && tlbState && (
       <div className="comparison-modal">
         <div className="modal-content">
           <div className="modal-header">
             <h3><Zap size={20} /> TLB State</h3>
             <button onClick={() => setShowTlb(false)} className="close-btn">×</button>
           </div>
           <div className="comparison-table">
             {tlbState.stats && (
               <div className="tlb-stats">
                 <div className="stat-item">
                   <div className="stat-label">TLB Hits</div>
                   <div className="stat-value">{tlbState.stats.hits}</div>
                 </div>
                 <div className="stat-item">
                   <div className="stat-label">TLB Misses</div>
                   <div className="stat-value">{tlbState.stats.misses}</div>
                 </div>
                 <div className="stat-item">
                   <div className="stat-label">Hit Ratio</div>
                   <div className="stat-value">{(tlbState.stats.hit_ratio * 100).toFixed(2)}%</div>
                 </div>
               </div>
             )}
             <h4>TLB Entries</h4>
             {tlbState.tlb && (
               <table>
                 <thead>
                   <tr>
                     <th>PID_Page</th>
                     <th>Frame</th>
                   </tr>
                 </thead>
                 <tbody>
                   {Object.entries(tlbState.tlb).map(([key, frame]) => (
                     <tr key={key}>
                       <td>{key}</td>
                       <td>{frame}</td>
                     </tr>
                   ))}
                 </tbody>
               </table>
             )}
           </div>
         </div>
       </div>
     )}

     {showWorkingSets && workingSets && (
       <div className="comparison-modal">
         <div className="modal-content">
           <div className="modal-header">
             <h3><Layers size={20} /> Working Sets</h3>
             <button onClick={() => setShowWorkingSets(false)} className="close-btn">×</button>
           </div>
           <div className="comparison-table">
             {Object.entries(workingSets).map(([pid, ws]) => (
               <div key={pid} className="working-set-info">
                 <h4>Process {pid}</h4>
                 <div className="ws-stats">
                   <span>Working Set Size: {ws.size}</span>
                   <span>Pages: {(ws.current_set || []).join(', ') || 'None'}</span>
                 </div>
               </div>
             ))}
           </div>
         </div>
       </div>
     )}
   </div>
 );
}

export default App;