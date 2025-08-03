from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import time
import threading
from collections import OrderedDict
import random
import math
import os

app = Flask(__name__)
prod_origin = os.environ.get('APP_URL')

allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001"
]

if prod_origin:
    allowed_origins.append(prod_origin)

CORS(app, origins=allowed_origins)

class VirtualMemorySimulator:
    def __init__(self, physical_frames=20, page_size=4096, virtual_pages=32):
        self.physical_frames = physical_frames
        self.page_size = page_size
        self.virtual_pages = virtual_pages
        
        self.physical_memory = [None] * physical_frames
        self.free_frames = list(range(physical_frames))
        self.processes = {}
        self.current_pid = 1
        
        self.stats = {
            'page_faults': 0,
            'memory_accesses': 0,
            'hit_ratio': 0.0,
            'algorithm_stats': {},
            'page_fault_history': [],
            'access_history': [],
            'working_set_sizes': {},
            'thrashing_detected': False
        }
        
        self.current_algorithm = 'FIFO'
        self.fifo_queue = []
        self.lru_access_order = {}
        self.clock_pointer = 0
        self.clock_bits = {}
        
        self.tlb = OrderedDict()
        self.tlb_hits = 0
        self.tlb_misses = 0
        self.tlb_size = 4
        
        self.performance_comparison = {
            'FIFO': {'page_faults': 0, 'accesses': 0},
            'LRU': {'page_faults': 0, 'accesses': 0},
            'Clock': {'page_faults': 0, 'accesses': 0},
            'Optimal': {'page_faults': 0, 'accesses': 0}
        }

    def _make_key(self, pid, page):
        return f"{pid}_{page}"

    def _parse_key(self, key):
        parts = key.split('_')
        return int(parts[0]), int(parts[1])
        
    def create_process(self, pid, pages_needed):
        if str(pid) in self.processes:
            return False
            
        if pages_needed > self.physical_frames:
            pages_needed = self.physical_frames
            
        page_table = {}
        allocated_pages = min(pages_needed, len(self.free_frames))
        
        for i in range(allocated_pages):
            if self.free_frames:
                frame = self.free_frames.pop(0)
                page_table[str(i)] = {
                    'frame': frame,
                    'valid': True,
                    'dirty': False,
                    'referenced': True,
                    'access_time': time.time(),
                    'load_time': time.time()
                }
                self.physical_memory[frame] = {'pid': pid, 'page': i}
                
                key = self._make_key(pid, i)
                if self.current_algorithm == 'FIFO':
                    self.fifo_queue.append((pid, i, frame))
                elif self.current_algorithm == 'Clock':
                    self.clock_bits[key] = 1
                elif self.current_algorithm == 'LRU':
                    self.lru_access_order[key] = time.time()
                    
        for i in range(allocated_pages, pages_needed):
            page_table[str(i)] = {
                'frame': None,
                'valid': False,
                'dirty': False,
                'referenced': False,
                'access_time': None,
                'load_time': None
            }
            
        self.processes[str(pid)] = {
            'page_table': page_table,
            'pages_needed': pages_needed,
            'allocated_pages': allocated_pages,
            'working_set': [],
            'recent_accesses': [],
            'creation_time': time.time()
        }
        
        self.stats['working_set_sizes'][str(pid)] = 0
        return True
        
    def terminate_process(self, pid):
        pid_str = str(pid)
        if pid_str not in self.processes:
            return False
            
        process = self.processes[pid_str]
        
        if self.current_algorithm == 'FIFO':
            self.fifo_queue = [(p, pg, f) for p, pg, f in self.fifo_queue if p != pid]

        for page_num_str, page_entry in process['page_table'].items():
            page_num = int(page_num_str)
            if page_entry['valid']:
                frame = page_entry['frame']
                self.physical_memory[frame] = None
                self.free_frames.append(frame)
                
                key = self._make_key(pid, page_num)
                if self.current_algorithm == 'LRU':
                    if key in self.lru_access_order:
                        del self.lru_access_order[key]
                elif self.current_algorithm == 'Clock':
                    if key in self.clock_bits:
                        del self.clock_bits[key]
                        
        self.clear_tlb_for_process(pid)
        del self.processes[pid_str]
        if pid_str in self.stats['working_set_sizes']:
            del self.stats['working_set_sizes'][pid_str]
        self.free_frames.sort()
        return True

    def translate_address(self, pid, virtual_address, future_accesses=None):
        pid_str = str(pid)
        if pid_str not in self.processes:
            return None, "Process not found"
            
        page_number = virtual_address // self.page_size
        offset = virtual_address % self.page_size
        
        if page_number >= self.processes[pid_str]['pages_needed']:
            return None, "Segmentation fault: Address out of bounds"
            
        self.stats['memory_accesses'] += 1
        if self.current_algorithm in self.performance_comparison:
            self.performance_comparison[self.current_algorithm]['accesses'] += 1
        
        tlb_key = self._make_key(pid, page_number)
        if tlb_key in self.tlb:
            self.tlb_hits += 1
            frame = self.tlb[tlb_key]
            self.tlb.move_to_end(tlb_key)
            physical_address = frame * self.page_size + offset
            self.update_access_info(pid, page_number)
            self.record_access(pid, page_number, False, True)
            return {
                'physical_address': physical_address, 'frame': frame, 'page_fault': False, 'tlb_hit': True,
                'translation_steps': [
                    {'step': 'tlb_lookup', 'description': f'TLB Hit for page {page_number}.'},
                    {'step': 'address_calculation', 'description': f'Physical Address = (Frame {frame} * Page Size) + Offset {offset} = {physical_address}'}
                ]
            }, None
        
        self.tlb_misses += 1
        page_table = self.processes[pid_str]['page_table']
        
        if str(page_number) not in page_table:
             return None, "Segmentation fault: Page not in page table"

        page_entry = page_table[str(page_number)]
        
        translation_steps = [
            {'step': 'tlb_lookup', 'description': f'TLB Miss for page {page_number}.'},
            {'step': 'page_table_lookup', 'description': f'Checking page table for page {page_number}.'}
        ]
        
        page_faulted = False
        if not page_entry['valid']:
            self.stats['page_faults'] += 1
            if self.current_algorithm in self.performance_comparison:
                self.performance_comparison[self.current_algorithm]['page_faults'] += 1
            translation_steps.append({'step': 'page_fault', 'description': f'Page Fault for page {page_number}.'})
            page_faulted = True
            
            fault_info = self.handle_page_fault(pid, page_number, future_accesses)
            translation_steps.extend(fault_info['steps'])
            page_entry = self.processes[pid_str]['page_table'][str(page_number)]
            self.record_access(pid, page_number, True, False)
            
        if page_entry['valid']:
            self.update_access_info(pid, page_number)
            self.update_tlb(pid, page_number, page_entry['frame'])
            
            physical_address = page_entry['frame'] * self.page_size + offset
            self.update_hit_ratio()
            self.update_working_set(pid, page_number)
            self.detect_thrashing()
            
            translation_steps.append({
                'step': 'address_calculation', 
                'description': f'Physical Address = (Frame {page_entry["frame"]} * {self.page_size}) + {offset} = {physical_address}'
            })
            
            if not page_faulted:
                self.record_access(pid, page_number, False, False)
            
            return {
                'physical_address': physical_address, 'frame': page_entry['frame'],
                'page_fault': page_faulted, 'tlb_hit': False,
                'translation_steps': translation_steps
            }, None
            
        return None, "Failed to handle page fault"

    def handle_page_fault(self, pid, page_number, future_accesses=None):
        steps = []
        
        if not self.free_frames:
            victim_info = self.select_victim_page(pid, future_accesses)
            if victim_info:
                evict_steps = self.evict_page(victim_info)
                steps.extend(evict_steps)
            else:
                steps.append({'step': 'error', 'description': 'No victim page could be selected.'})
                return {'steps': steps}
                
        if self.free_frames:
            frame = self.free_frames.pop(0)
            
            self.processes[str(pid)]['page_table'][str(page_number)].update({
                'frame': frame, 'valid': True, 'dirty': False, 'referenced': True,
                'access_time': time.time(), 'load_time': time.time()
            })
            
            self.physical_memory[frame] = {'pid': pid, 'page': page_number}
            
            key = self._make_key(pid, page_number)
            if self.current_algorithm == 'FIFO':
                self.fifo_queue.append((pid, page_number, frame))
            elif self.current_algorithm == 'Clock':
                self.clock_bits[key] = 1
            elif self.current_algorithm == 'LRU':
                self.lru_access_order[key] = time.time()
                
            steps.append({'step': 'page_load', 'description': f'Loaded page {page_number} of process {pid} into frame {frame}.'})
            
        return {'steps': steps}

    def select_victim_page(self, current_pid, future_accesses=None):
        if self.current_algorithm == 'FIFO':
            return self.select_fifo_victim()
        elif self.current_algorithm == 'LRU':
            return self.select_lru_victim()
        elif self.current_algorithm == 'Clock':
            return self.select_clock_victim()
        elif self.current_algorithm == 'Optimal':
            return self.select_optimal_victim(future_accesses)
        return None
        
    def select_fifo_victim(self):
        if self.fifo_queue:
            pid, page_num, frame = self.fifo_queue.pop(0)
            return {'frame': frame, 'pid': pid, 'page': page_num, 'reason': 'Selected oldest page from FIFO queue.'}
        return None
        
    def select_lru_victim(self):
        if self.lru_access_order:
            oldest_key = min(self.lru_access_order, key=self.lru_access_order.get)
            pid, page_num = self._parse_key(oldest_key)
            pid_str = str(pid)
            if pid_str in self.processes and str(page_num) in self.processes[pid_str]['page_table']:
                page_entry = self.processes[pid_str]['page_table'][str(page_num)]
                if page_entry['valid']:
                    del self.lru_access_order[oldest_key]
                    return {'frame': page_entry['frame'], 'pid': pid, 'page': page_num, 'reason': 'Selected least recently used (LRU) page.'}
        return None
        
    def select_clock_victim(self):
        start_pointer = self.clock_pointer
        while True:
            frame_info = self.physical_memory[self.clock_pointer]
            if frame_info:
                pid, page_num = frame_info['pid'], frame_info['page']
                key = self._make_key(pid, page_num)
                
                if self.clock_bits.get(key, 0) == 0:
                    victim_frame = self.clock_pointer
                    self.clock_pointer = (self.clock_pointer + 1) % self.physical_frames
                    if key in self.clock_bits: del self.clock_bits[key]
                    return {'frame': victim_frame, 'pid': pid, 'page': page_num, 'reason': f'Found page with reference bit 0 at frame {victim_frame}.'}
                else:
                    self.clock_bits[key] = 0
            
            self.clock_pointer = (self.clock_pointer + 1) % self.physical_frames
            if self.clock_pointer == start_pointer:
                return self.select_fifo_victim()
        
    def select_optimal_victim(self, future_accesses):
        if not future_accesses:
            return self.select_fifo_victim()

        pages_in_memory = [pm for pm in self.physical_memory if pm is not None]
        
        future_use = {}
        for mem_page in pages_in_memory:
            key = self._make_key(mem_page['pid'], mem_page['page'])
            try:
                next_use = next(i for i, (p, pg) in enumerate(future_accesses) if p == mem_page['pid'] and pg == mem_page['page'])
                future_use[key] = next_use
            except StopIteration:
                frame_idx = self.processes[str(mem_page['pid'])]['page_table'][str(mem_page['page'])]['frame']
                return {'frame': frame_idx, 'pid': mem_page['pid'], 'page': mem_page['page'], 'reason': 'Page will not be used again in the future.'}

        if not future_use:
            return self.select_fifo_victim()
            
        victim_key = max(future_use, key=future_use.get)
        pid, page = self._parse_key(victim_key)
        frame_idx = self.processes[str(pid)]['page_table'][str(page)]['frame']
        return {'frame': frame_idx, 'pid': pid, 'page': page, 'reason': f'Page is used furthest in the future at step {future_use[victim_key]}.'}
        
    def evict_page(self, victim_info):
        steps = []
        frame = victim_info['frame']
        pid = victim_info['pid']
        page_num = victim_info['page']
        
        steps.append({'step': 'victim_selection', 'description': victim_info.get('reason', f'Evicting page {page_num} of P{pid} from frame {frame}.')})
        
        pid_str = str(pid)
        if pid_str in self.processes:
            page_entry = self.processes[pid_str]['page_table'][str(page_num)]
            if page_entry.get('dirty', False):
                steps.append({'step': 'write_back', 'description': f'Writing dirty page {page_num} back to disk.'})
            
            page_entry['valid'] = False
            page_entry['frame'] = None
            
        self.physical_memory[frame] = None
        self.free_frames.append(frame)
        self.free_frames.sort()
        
        self.clear_tlb_entry(pid, page_num)
        
        return steps
        
    def update_access_info(self, pid, page_number):
        current_time = time.time()
        key = self._make_key(pid, page_number)
        
        if self.current_algorithm == 'LRU':
            self.lru_access_order[key] = current_time
        elif self.current_algorithm == 'Clock':
            self.clock_bits[key] = 1
            
        pid_str = str(pid)
        if pid_str in self.processes and str(page_number) in self.processes[pid_str]['page_table']:
            self.processes[pid_str]['page_table'][str(page_number)]['access_time'] = current_time
            self.processes[pid_str]['page_table'][str(page_number)]['referenced'] = True
            
    def update_tlb(self, pid, page_number, frame):
        tlb_key = self._make_key(pid, page_number)
        if tlb_key in self.tlb:
            del self.tlb[tlb_key]
        self.tlb[tlb_key] = frame
        
        if len(self.tlb) > self.tlb_size:
            self.tlb.popitem(last=False)
            
    def clear_tlb_for_process(self, pid):
        keys_to_remove = [k for k in self.tlb if k.startswith(f"{pid}_")]
        for key in keys_to_remove:
            del self.tlb[key]
            
    def clear_tlb_entry(self, pid, page_number):
        tlb_key = self._make_key(pid, page_number)
        if tlb_key in self.tlb:
            del self.tlb[tlb_key]
            
    def update_working_set(self, pid, page_number):
        pid_str = str(pid)
        if pid_str not in self.processes:
            return
            
        current_time = time.time()
        window_size = 10.0
        
        process = self.processes[pid_str]
        process['recent_accesses'].append((page_number, current_time))
        process['recent_accesses'] = [(p, t) for p, t in process['recent_accesses'] if current_time - t <= window_size]
        process['working_set'] = list(set(p for p, t in process['recent_accesses']))
        self.stats['working_set_sizes'][pid_str] = len(process['working_set'])
        
    def detect_thrashing(self):
        history = self.stats.get('page_fault_history', [])
        if len(history) < 20:
            self.stats['thrashing_detected'] = False
            return
            
        recent_fault_count = sum(1 for f in history[-20:])
        self.stats['thrashing_detected'] = recent_fault_count > 10

    def record_access(self, pid, page_number, was_fault, was_tlb_hit):
        current_time = time.time()
        self.stats['access_history'].append({
            'pid': pid, 'page': page_number, 'time': current_time, 'fault': was_fault, 'tlb_hit': was_tlb_hit
        })
        
        if was_fault:
            self.stats['page_fault_history'].append({
                'pid': pid, 'page': page_number, 'time': current_time, 'algorithm': self.current_algorithm
            })
            
        if len(self.stats['access_history']) > 200:
            self.stats['access_history'] = self.stats['access_history'][-100:]
        if len(self.stats['page_fault_history']) > 200:
            self.stats['page_fault_history'] = self.stats['page_fault_history'][-100:]
            
    def update_hit_ratio(self):
        if self.stats['memory_accesses'] > 0:
            hits = self.stats['memory_accesses'] - self.stats['page_faults']
            self.stats['hit_ratio'] = hits / self.stats['memory_accesses']
            
    def get_algorithm_comparison(self):
        comparison = {}
        for algo, stats in self.performance_comparison.items():
            if stats['accesses'] > 0:
                fault_rate = stats['page_faults'] / stats['accesses']
                comparison[algo] = {'page_faults': stats['page_faults'], 'accesses': stats['accesses'], 'fault_rate': fault_rate, 'hit_rate': 1 - fault_rate}
            else:
                comparison[algo] = {'page_faults': 0, 'accesses': 0, 'fault_rate': 0, 'hit_rate': 1.0}
        return comparison
        
    def generate_report(self):
        total_accesses = self.stats['memory_accesses']
        total_tlb_lookups = self.tlb_hits + self.tlb_misses
        return {
            'system_info': {
                'total_frames': self.physical_frames, 'used_frames': self.physical_frames - len(self.free_frames),
                'free_frames': len(self.free_frames), 'page_size': self.page_size,
                'current_algorithm': self.current_algorithm
            },
            'performance_stats': {
                'total_accesses': total_accesses, 'page_faults': self.stats['page_faults'],
                'hit_ratio': self.stats['hit_ratio'], 'tlb_hits': self.tlb_hits,
                'tlb_misses': self.tlb_misses,
                'tlb_hit_ratio': self.tlb_hits / total_tlb_lookups if total_tlb_lookups > 0 else 0
            },
            'algorithm_comparison': self.get_algorithm_comparison(),
            'working_sets': self.stats.get('working_set_sizes', {}),
            'thrashing_detected': self.stats.get('thrashing_detected', False),
            'process_info': {pid: {
                'pages_allocated': proc['allocated_pages'], 'pages_needed': proc['pages_needed'],
                'working_set_size': len(proc.get('working_set', []))
            } for pid, proc in self.processes.items()}
        }
        
    def get_memory_state(self):
        total_tlb_lookups = self.tlb_hits + self.tlb_misses
        return {
            'physical_memory': self.physical_memory,
            'processes': {pid: {
                'page_table': proc['page_table'], 'pages_needed': proc['pages_needed'],
                'allocated_pages': proc['allocated_pages'],
                'working_set_size': self.stats['working_set_sizes'].get(pid, 0)
            } for pid, proc in self.processes.items()},
            'free_frames': self.free_frames, 'stats': self.stats,
            'current_algorithm': self.current_algorithm, 'tlb': dict(self.tlb),
            'tlb_stats': {
                'hits': self.tlb_hits, 'misses': self.tlb_misses,
                'hit_ratio': self.tlb_hits / total_tlb_lookups if total_tlb_lookups > 0 else 0
            }
        }

simulator = VirtualMemorySimulator()

@app.route('/api/create_process', methods=['POST'])
def create_process_route():
    try:
        data = request.json or {}
        pid = data.get('pid', simulator.current_pid)
        pages = data.get('pages', 4)
        
        success = simulator.create_process(pid, pages)
        if success:
            simulator.current_pid = max(simulator.current_pid, pid) + 1
        
        return jsonify({'success': success, 'memory_state': simulator.get_memory_state()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/terminate_process', methods=['POST'])
def terminate_process_route():
    try:
        pid = request.json.get('pid')
        if pid is None:
            return jsonify({'success': False, 'error': 'PID is required.'}), 400
        success = simulator.terminate_process(int(pid))
        
        return jsonify({'success': success, 'memory_state': simulator.get_memory_state()})
    except (ValueError, KeyError) as e:
        return jsonify({'success': False, 'error': 'Invalid PID format or process not found.'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/access_address', methods=['POST'])
def access_address_route():
    try:
        data = request.json
        pid = data.get('pid')
        virtual_address = data.get('virtual_address')
        
        if pid is None or virtual_address is None:
            return jsonify({'result': None, 'error': 'PID and virtual_address are required.'}), 400

        result, error_msg = simulator.translate_address(int(pid), int(virtual_address))
        if error_msg:
             return jsonify({'result': None, 'error': error_msg, 'memory_state': simulator.get_memory_state()}), 400
        
        return jsonify({'result': result, 'memory_state': simulator.get_memory_state()})
    except Exception as e:
        return jsonify({'result': None, 'error': str(e)}), 500

@app.route('/api/set_algorithm', methods=['POST'])
def set_algorithm_route():
    try:
        algorithm = request.json.get('algorithm')
        if algorithm not in ['FIFO', 'LRU', 'Clock', 'Optimal']:
            return jsonify({'success': False, 'error': 'Invalid algorithm specified.'}), 400
            
        simulator.current_algorithm = algorithm
        simulator.fifo_queue.clear()
        simulator.lru_access_order.clear()
        simulator.clock_pointer = 0
        simulator.clock_bits.clear()
        
        for frame_idx, frame_content in enumerate(simulator.physical_memory):
            if frame_content:
                pid, page_num = frame_content['pid'], frame_content['page']
                key = simulator._make_key(pid, page_num)
                if algorithm == 'FIFO':
                    simulator.fifo_queue.append((pid, page_num, frame_idx))
                elif algorithm == 'Clock':
                    simulator.clock_bits[key] = 1
                elif algorithm == 'LRU':
                    access_time = simulator.processes[str(pid)]['page_table'][str(page_num)].get('access_time', time.time())
                    simulator.lru_access_order[key] = access_time
        
        if algorithm == 'FIFO':
             get_load_time = lambda item: simulator.processes[str(item[0])]['page_table'][str(item[1])].get('load_time', 0)
             simulator.fifo_queue.sort(key=get_load_time)

        return jsonify({'success': True, 'memory_state': simulator.get_memory_state()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_simulator_route():
    try:
        global simulator
        simulator = VirtualMemorySimulator()
        return jsonify({'success': True, 'memory_state': simulator.get_memory_state()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/memory_state', methods=['GET'])
def get_memory_state_route():
    try:
        return jsonify(simulator.get_memory_state())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/run_demo', methods=['POST'])
def run_demo_route():
    try:
        demo_results = []
        
        if not simulator.processes:
            simulator.create_process(1, 10)
            simulator.create_process(2, 10)
        
        access_sequence = [
            (1, 0x1000), (1, 0x2000), (2, 0x1000), (1, 0x3000),
            (2, 0x2000), (1, 0x4000), (2, 0x3000), (1, 0x1000),
            (1, 0x5000), (2, 0x4000)
        ]
        
        for pid, addr in access_sequence:
            result, error = simulator.translate_address(pid, addr)
            demo_results.append({'pid': pid, 'virtual_address': addr, 'result': result, 'error': error})
        
        return jsonify({ 'success': True, 'memory_state': simulator.get_memory_state(), 'demo_results': demo_results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/compare_algorithms', methods=['POST'])
def compare_algorithms_route():
    try:
        data = request.json or {}
        sequences = data.get('sequences')
        frames = data.get('frames', 10)
        
        if not sequences:
            return jsonify({'success': False, 'error': 'Test sequences are required.'}), 400
            
        results = {}
        algorithms = ['FIFO', 'LRU', 'Clock', 'Optimal']
        
        page_size = 4096
        future_page_accesses = [(pid, addr // page_size) for pid, addr in sequences]

        for algorithm in algorithms:
            try:
                temp_sim = VirtualMemorySimulator(physical_frames=frames, page_size=page_size)
                temp_sim.current_algorithm = algorithm
                
                pids_in_sequences = sorted(list(set(pid for pid, addr in sequences)))
                for pid in pids_in_sequences:
                    temp_sim.create_process(pid, 32)
                
                for i, (pid, addr) in enumerate(sequences):
                    if algorithm == 'Optimal':
                        remaining_accesses = future_page_accesses[i+1:]
                        temp_sim.translate_address(pid, addr, future_accesses=remaining_accesses)
                    else:
                        temp_sim.translate_address(pid, addr)
                
                stats = temp_sim.stats
                accesses = stats['memory_accesses']
                faults = stats['page_faults']
                results[algorithm] = {
                    'page_faults': faults, 'accesses': accesses,
                    'hit_ratio': stats['hit_ratio'],
                    'fault_rate': faults / accesses if accesses > 0 else 0
                }
            except Exception as e:
                results[algorithm] = {'error': str(e)}
        
        return jsonify({'success': True, 'comparison_results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/generate_report', methods=['GET'])
def generate_report_route():
    try:
        report = simulator.generate_report()
        return jsonify({'success': True, 'report': report})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/random_access', methods=['POST'])
def random_access_route():
    try:
        count = int(request.json.get('count', 10))
        results = []
        pids = list(simulator.processes.keys())
        
        if not pids:
            return jsonify({'success': False, 'error': 'No active processes to access.'}), 400
        
        for _ in range(count):
            pid = int(random.choice(pids))
            process = simulator.processes[str(pid)]
            max_addr = process['pages_needed'] * simulator.page_size - 1
            addr = random.randint(0, max_addr)
            
            result, error = simulator.translate_address(pid, addr)
            results.append({'pid': pid, 'virtual_address': addr, 'result': result, 'error': error})
        
        return jsonify({'success': True, 'memory_state': simulator.get_memory_state(), 'access_results': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check_route():
    return jsonify({'status': 'healthy', 'message': 'Virtual memory simulator is running.'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)