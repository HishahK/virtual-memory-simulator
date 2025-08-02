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
     
     self.tlb = {}
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
     if pid in self.processes:
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
             
             if self.current_algorithm == 'FIFO':
                 self.fifo_queue.append((pid, i, frame))
             elif self.current_algorithm == 'Clock':
                 self.clock_bits[self._make_key(pid, i)] = 1
             elif self.current_algorithm == 'LRU':
                 self.lru_access_order[self._make_key(pid, i)] = time.time()
                 
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
     
     for page_num_str, page_entry in process['page_table'].items():
         page_num = int(page_num_str)
         if page_entry['valid']:
             frame = page_entry['frame']
             self.physical_memory[frame] = None
             self.free_frames.append(frame)
             
             if self.current_algorithm == 'FIFO':
                 self.fifo_queue = [(p, pg, f) for p, pg, f in self.fifo_queue 
                                  if not (p == pid and pg == page_num)]
             elif self.current_algorithm == 'LRU':
                 key = self._make_key(pid, page_num)
                 if key in self.lru_access_order:
                     del self.lru_access_order[key]
             elif self.current_algorithm == 'Clock':
                 key = self._make_key(pid, page_num)
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
         return None
         
     page_number = virtual_address // self.page_size
     offset = virtual_address % self.page_size
     
     if page_number >= self.processes[pid_str]['pages_needed']:
         return None
         
     self.stats['memory_accesses'] += 1
     self.performance_comparison[self.current_algorithm]['accesses'] += 1
     
     tlb_key = self._make_key(pid, page_number)
     if tlb_key in self.tlb:
         self.tlb_hits += 1
         frame = self.tlb[tlb_key]
         physical_address = frame * self.page_size + offset
         self.update_access_info(pid, page_number)
         self.record_access(pid, page_number, False, True)
         return {
             'physical_address': physical_address,
             'frame': frame,
             'page_fault': False,
             'tlb_hit': True,
             'translation_steps': [
                 {'step': 'tlb_lookup', 'description': f'tlb hit for page {page_number}'},
                 {'step': 'address_calculation', 'description': f'physical address = frame {frame} * page size + offset'}
             ]
         }
     
     self.tlb_misses += 1
     page_entry = self.processes[pid_str]['page_table'][str(page_number)]
     
     translation_steps = [
         {'step': 'tlb_lookup', 'description': f'tlb miss for page {page_number}'},
         {'step': 'page_table_lookup', 'description': f'checking page table for page {page_number}'}
     ]
     
     if not page_entry['valid']:
         self.stats['page_faults'] += 1
         self.performance_comparison[self.current_algorithm]['page_faults'] += 1
         translation_steps.append({'step': 'page_fault', 'description': f'page fault occurred for page {page_number}'})
         
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
             'description': f'physical address = frame {page_entry["frame"]} * {self.page_size} + {offset} = {physical_address}'
         })
         
         if not any(step['step'] == 'page_fault' for step in translation_steps):
             self.record_access(pid, page_number, False, False)
         
         return {
             'physical_address': physical_address,
             'frame': page_entry['frame'],
             'page_fault': any(step['step'] == 'page_fault' for step in translation_steps),
             'tlb_hit': False,
             'translation_steps': translation_steps
         }
         
     return None

 def handle_page_fault(self, pid, page_number, future_accesses=None):
     steps = []
     
     if not self.free_frames:
         victim_info = self.select_victim_page(future_accesses)
         if victim_info:
             evict_steps = self.evict_page(victim_info['frame'])
             steps.extend(evict_steps)
             
     if self.free_frames:
         frame = self.free_frames.pop(0)
         
         self.processes[str(pid)]['page_table'][str(page_number)] = {
             'frame': frame,
             'valid': True,
             'dirty': False,
             'referenced': True,
             'access_time': time.time(),
             'load_time': time.time()
         }
         
         self.physical_memory[frame] = {'pid': pid, 'page': page_number}
         
         if self.current_algorithm == 'FIFO':
             self.fifo_queue.append((pid, page_number, frame))
         elif self.current_algorithm == 'Clock':
             self.clock_bits[self._make_key(pid, page_number)] = 1
         elif self.current_algorithm == 'LRU':
             self.lru_access_order[self._make_key(pid, page_number)] = time.time()
             
         steps.append({'step': 'page_load', 'description': f'loaded page {page_number} into frame {frame}'})
         
     return {'steps': steps}

 def select_victim_page(self, future_accesses=None):
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
         return {'frame': frame, 'pid': pid, 'page': page_num, 'reason': 'oldest page in fifo queue'}
     return None
     
 def select_lru_victim(self):
     if self.lru_access_order:
         oldest_key = min(self.lru_access_order.items(), key=lambda x: x[1])[0]
         pid, page_num = self._parse_key(oldest_key)
         pid_str = str(pid)
         if pid_str in self.processes and str(page_num) in self.processes[pid_str]['page_table']:
             page_entry = self.processes[pid_str]['page_table'][str(page_num)]
             if page_entry['valid']:
                 del self.lru_access_order[oldest_key]
                 return {'frame': page_entry['frame'], 'pid': pid, 'page': page_num, 'reason': 'least recently used'}
     return None
     
 def select_clock_victim(self):
     checked = 0
     max_checks = self.physical_frames * 2
     
     while checked < max_checks:
         frame_info = self.physical_memory[self.clock_pointer]
         if frame_info:
             pid = frame_info['pid']
             page_num = frame_info['page']
             key = self._make_key(pid, page_num)

             if key in self.clock_bits:
                 if self.clock_bits[key] == 0:
                     del self.clock_bits[key]
                     victim_frame = self.clock_pointer
                     self.clock_pointer = (self.clock_pointer + 1) % self.physical_frames
                     return {'frame': victim_frame, 'pid': pid, 'page': page_num, 'reason': 'clock hand found page with reference bit 0'}
                 else:
                     self.clock_bits[key] = 0
         
         self.clock_pointer = (self.clock_pointer + 1) % self.physical_frames
         checked += 1
     
     if self.fifo_queue:
         pid, page_num, frame = self.fifo_queue.pop(0)
         return {'frame': frame, 'pid': pid, 'page': page_num, 'reason': 'clock fallback to fifo'}
     return None
     
 def select_optimal_victim(self, future_accesses):
     if not future_accesses:
         return self.select_fifo_victim()

     pages_in_memory = []
     for frame_idx, frame_content in enumerate(self.physical_memory):
         if frame_content:
             pages_in_memory.append({
                 'pid': frame_content['pid'],
                 'page': frame_content['page'],
                 'frame': frame_idx
             })

     victim = None
     latest_use_time = -1

     for mem_page in pages_in_memory:
         try:
             future_use_index = future_accesses.index((mem_page['pid'], mem_page['page']))
             if future_use_index > latest_use_time:
                 latest_use_time = future_use_index
                 victim = mem_page
         except ValueError:
             return {'frame': mem_page['frame'], 'pid': mem_page['pid'], 'page': mem_page['page'], 'reason': 'page not used in future'}

     if victim:
          return {'frame': victim['frame'], 'pid': victim['pid'], 'page': victim['page'], 'reason': f'page used furthest in future at index {latest_use_time}'}
     
     return self.select_fifo_victim()
     
 def evict_page(self, frame):
     steps = []
     if self.physical_memory[frame]:
         victim_info = self.physical_memory[frame]
         pid = victim_info['pid']
         page_num = victim_info['page']
         
         steps.append({'step': 'eviction', 'description': f'evicting page {page_num} from process {pid} (frame {frame})'})
         
         pid_str = str(pid)
         if pid_str in self.processes:
             page_entry = self.processes[pid_str]['page_table'][str(page_num)]
             if page_entry.get('dirty', False):
                 steps.append({'step': 'write_back', 'description': f'writing dirty page {page_num} back to storage'})
             
             self.processes[pid_str]['page_table'][str(page_num)]['valid'] = False
             self.processes[pid_str]['page_table'][str(page_num)]['frame'] = None
             
         self.physical_memory[frame] = None
         self.free_frames.append(frame)
         self.free_frames.sort()
         
         self.clear_tlb_entry(pid, page_num)
         
     return steps
     
 def update_access_info(self, pid, page_number):
     current_time = time.time()
     
     if self.current_algorithm == 'LRU':
         key = self._make_key(pid, page_number)
         self.lru_access_order[key] = current_time
     elif self.current_algorithm == 'Clock':
         key = self._make_key(pid, page_number)
         self.clock_bits[key] = 1
         
     pid_str = str(pid)
     if pid_str in self.processes and str(page_number) in self.processes[pid_str]['page_table']:
         self.processes[pid_str]['page_table'][str(page_number)]['access_time'] = current_time
         self.processes[pid_str]['page_table'][str(page_number)]['referenced'] = True
         
 def update_tlb(self, pid, page_number, frame):
     tlb_key = self._make_key(pid, page_number)
     self.tlb[tlb_key] = frame
     
     if len(self.tlb) > self.tlb_size:
         oldest_key = next(iter(self.tlb))
         del self.tlb[oldest_key]
         
 def clear_tlb_for_process(self, pid):
     keys_to_remove = [k for k in self.tlb.keys() if k.startswith(f"{pid}_")]
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
     
     process['recent_accesses'] = [(p, t) for p, t in process['recent_accesses'] 
                                 if current_time - t <= window_size]
     
     process['working_set'] = list(set(p for p, t in process['recent_accesses']))
     self.stats['working_set_sizes'][pid_str] = len(process['working_set'])
     
 def detect_thrashing(self):
     if len(self.stats.get('page_fault_history', [])) < 20:
         return
         
     recent_fault_count = sum(1 for f in self.stats['page_fault_history'][-20:])
     self.stats['thrashing_detected'] = recent_fault_count > 10

 def record_access(self, pid, page_number, was_fault, was_tlb_hit):
     current_time = time.time()
     
     self.stats['access_history'].append({
         'pid': pid,
         'page': page_number,
         'time': current_time,
         'fault': was_fault,
         'tlb_hit': was_tlb_hit
     })
     
     if was_fault:
         self.stats['page_fault_history'].append({
             'pid': pid,
             'page': page_number,
             'time': current_time,
             'algorithm': self.current_algorithm
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
             comparison[algo] = {
                 'page_faults': stats['page_faults'],
                 'accesses': stats['accesses'],
                 'fault_rate': fault_rate,
                 'hit_rate': 1 - fault_rate
             }
         else:
             comparison[algo] = {
                 'page_faults': 0, 'accesses': 0, 'fault_rate': 0, 'hit_rate': 0
             }
     return comparison
     
 def generate_report(self):
     total_frames = self.physical_frames
     used_frames = total_frames - len(self.free_frames)
     
     return {
         'system_info': {
             'total_frames': total_frames, 'used_frames': used_frames,
             'free_frames': len(self.free_frames), 'page_size': self.page_size,
             'current_algorithm': self.current_algorithm
         },
         'performance_stats': {
             'total_accesses': self.stats['memory_accesses'],
             'page_faults': self.stats['page_faults'],
             'hit_ratio': self.stats['hit_ratio'], 'tlb_hits': self.tlb_hits,
             'tlb_misses': self.tlb_misses,
             'tlb_hit_ratio': self.tlb_hits / (self.tlb_hits + self.tlb_misses) if (self.tlb_hits + self.tlb_misses) > 0 else 0
         },
         'algorithm_comparison': self.get_algorithm_comparison(),
         'working_sets': self.stats.get('working_set_sizes', {}),
         'thrashing_detected': self.stats.get('thrashing_detected', False),
         'process_info': {
             pid: {
                 'pages_allocated': proc['allocated_pages'],
                 'pages_needed': proc['pages_needed'],
                 'working_set_size': len(proc.get('working_set', []))
             } for pid, proc in self.processes.items()
         }
     }
     
 def get_memory_state(self):
     return {
         'physical_memory': self.physical_memory,
         'processes': {
             pid: {
                 'page_table': proc['page_table'],
                 'pages_needed': proc['pages_needed'],
                 'allocated_pages': proc['allocated_pages'],
                 'working_set_size': len(proc.get('working_set', []))
             } for pid, proc in self.processes.items()
         },
         'free_frames': self.free_frames,
         'stats': self.stats,
         'current_algorithm': self.current_algorithm,
         'tlb': dict(self.tlb),
         'tlb_stats': {
             'hits': self.tlb_hits, 'misses': self.tlb_misses,
             'hit_ratio': self.tlb_hits / (self.tlb_hits + self.tlb_misses) if (self.tlb_hits + self.tlb_misses) > 0 else 0
         }
     }

simulator = VirtualMemorySimulator()

@app.route('/api/create_process', methods=['POST'])
def create_process():
 try:
     data = request.json or {}
     pid = data.get('pid', simulator.current_pid)
     pages = data.get('pages', 4)
     
     success = simulator.create_process(pid, pages)
     if success:
         simulator.current_pid = max(simulator.current_pid, pid) + 1
         
     return jsonify({
         'success': success, 'memory_state': simulator.get_memory_state()
     })
 except Exception as e:
     return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/terminate_process', methods=['POST'])
def terminate_process():
 try:
     data = request.json or {}
     pid = data.get('pid')
     if pid is None:
         return jsonify({'success': False, 'error': 'pid is required'}), 400
     success = simulator.terminate_process(int(pid))
     
     return jsonify({
         'success': success, 'memory_state': simulator.get_memory_state()
     })
 except Exception as e:
     return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/translate_address', methods=['POST'])
def translate_address():
 try:
     data = request.json or {}
     pid = data.get('pid')
     virtual_address = data.get('virtual_address')
     
     if pid is None or virtual_address is None:
         return jsonify({'result': None, 'error': 'pid and virtual_address are required'}), 400

     result = simulator.translate_address(int(pid), int(virtual_address))
     
     return jsonify({
         'result': result, 'memory_state': simulator.get_memory_state()
     })
 except Exception as e:
     return jsonify({'result': None, 'error': str(e)}), 500

@app.route('/api/set_algorithm', methods=['POST'])
def set_algorithm():
 try:
     data = request.json or {}
     algorithm = data.get('algorithm')
     
     if algorithm not in ['FIFO', 'LRU', 'Clock', 'Optimal']:
         return jsonify({'success': False, 'error': 'invalid algorithm'}), 400
         
     simulator.current_algorithm = algorithm
     simulator.fifo_queue = []
     simulator.lru_access_order = {}
     simulator.clock_pointer = 0
     simulator.clock_bits = {}
     
     for frame_idx, frame_content in enumerate(simulator.physical_memory):
         if frame_content:
             pid, page_num = frame_content['pid'], frame_content['page']
             if algorithm == 'FIFO':
                 simulator.fifo_queue.append((pid, page_num, frame_idx))
             elif algorithm == 'Clock':
                 simulator.clock_bits[simulator._make_key(pid, page_num)] = 1
             elif algorithm == 'LRU':
                 access_time = simulator.processes[str(pid)]['page_table'][str(page_num)].get('access_time', time.time())
                 simulator.lru_access_order[simulator._make_key(pid, page_num)] = access_time
     
     return jsonify({
         'success': True, 'memory_state': simulator.get_memory_state()
     })
 except Exception as e:
     return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def reset_simulator():
 try:
     global simulator
     simulator = VirtualMemorySimulator()
     
     return jsonify({
         'success': True, 'memory_state': simulator.get_memory_state()
     })
 except Exception as e:
     return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/memory_state', methods=['GET'])
def get_memory_state():
 try:
     return jsonify(simulator.get_memory_state())
 except Exception as e:
     return jsonify({'error': str(e)}), 500

@app.route('/api/run_demo', methods=['POST'])
def run_demo():
 try:
     demo_results = []
     
     if not simulator.processes:
         simulator.create_process(1, 4)
         simulator.create_process(2, 4)
         simulator.create_process(3, 4)
     
     demo_sequences = [
         (1, 0x0000), (1, 0x1000), (2, 0x0000), (1, 0x2000),
         (2, 0x1000), (1, 0x3000), (2, 0x2000), (1, 0x0000),
         (3, 0x0000), (3, 0x1000), (1, 0x1000), (2, 0x3000),
         (3, 0x2000), (2, 0x0000), (1, 0x3000), (3, 0x3000)
     ]
     
     for pid, addr in demo_sequences:
         result = simulator.translate_address(pid, addr)
         demo_results.append({
             'pid': pid,
             'virtual_address': addr,
             'result': result
         })
     
     return jsonify({
         'success': True,
         'memory_state': simulator.get_memory_state(),
         'demo_results': demo_results
     })
 except Exception as e:
     return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/compare_algorithms', methods=['POST'])
def compare_algorithms():
   try:
       data = request.json or {}
       test_sequences = data.get('sequences', [])
       
       if not test_sequences:
           return jsonify({'success': False, 'error': 'test sequences are required'}), 400
           
       results = {}
       algorithms = ['FIFO', 'LRU', 'Clock', 'Optimal']
       
       page_size = 4096
       future_page_accesses = [(pid, addr // page_size) for pid, addr in test_sequences]

       for algorithm in algorithms:
           try:
               temp_simulator = VirtualMemorySimulator()
               temp_simulator.physical_frames = 3
               temp_simulator.current_algorithm = algorithm
               
               pids_in_sequences = set(pid for pid, addr in test_sequences)
               for pid in pids_in_sequences:
                   temp_simulator.create_process(pid, 10)
               
               for i, (pid, addr) in enumerate(test_sequences):
                   try:
                       if algorithm == 'Optimal':
                           remaining_accesses = future_page_accesses[i+1:]
                           temp_simulator.translate_address(pid, addr, future_accesses=remaining_accesses)
                       else:
                           temp_simulator.translate_address(pid, addr)
                   except Exception as e:
                       print(f"Error in {algorithm} at sequence {i}: {e}")
                       continue
               
               results[algorithm] = {
                   'page_faults': temp_simulator.stats['page_faults'],
                   'accesses': temp_simulator.stats['memory_accesses'],
                   'hit_ratio': temp_simulator.stats['hit_ratio'],
                   'fault_rate': temp_simulator.stats['page_faults'] / max(temp_simulator.stats['memory_accesses'], 1)
               }
               
           except Exception as e:
               print(f"Error testing algorithm {algorithm}: {e}")
               results[algorithm] = {
                   'page_faults': 0,
                   'accesses': 0,
                   'hit_ratio': 0,
                   'fault_rate': 0,
                   'error': str(e)
               }
       
       return jsonify({
           'success': True, 
           'comparison': results
       })
       
   except Exception as e:  
       print(f"Compare algorithms error: {e}")
       return jsonify({'success': False, 'error': str(e)}), 500



@app.route('/api/generate_report', methods=['GET'])
def generate_report():
 try:
     report = simulator.generate_report()
     return jsonify({
         'success': True,
         'report': report
     })
 except Exception as e:
     return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/working_sets', methods=['GET'])
def get_working_sets():
 try:
     working_sets = {}
     for pid, process in simulator.processes.items():
         working_sets[pid] = {
             'size': len(process.get('working_set', [])),
             'current_set': process.get('working_set', [])
         }
     
     return jsonify({
         'success': True,
         'working_sets': working_sets
     })
 except Exception as e:
     return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/tlb_state', methods=['GET'])
def get_tlb_state():
 try:
     return jsonify({
         'success': True,
         'tlb': dict(simulator.tlb),
         'stats': {
             'hits': simulator.tlb_hits,
             'misses': simulator.tlb_misses,
             'hit_ratio': simulator.tlb_hits / (simulator.tlb_hits + simulator.tlb_misses) if (simulator.tlb_hits + simulator.tlb_misses) > 0 else 0
         }
     })
 except Exception as e:
     return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/random_access', methods=['POST'])
def random_access():
 try:
     data = request.json or {}
     count = data.get('count', 10)
     
     results = []
     pids = list(simulator.processes.keys())
     
     if not pids:
         return jsonify({'success': False, 'error': 'no processes available'}), 400
     
     for _ in range(count):
         pid = random.choice([int(p) for p in pids])
         addr = random.randint(0, 0x7FFF)
         
         result = simulator.translate_address(pid, addr)
         results.append({
             'pid': pid,
             'virtual_address': addr,
             'result': result
         })
     
     return jsonify({
         'success': True,
         'memory_state': simulator.get_memory_state(),
         'results': results
     })
 except Exception as e:
     return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
 return jsonify({
     'status': 'healthy',
     'message': 'virtual memory simulator backend is running'
 })

if __name__ == '__main__':
  app.run(debug=False, host='0.0.0.0', port=5001)
else:
  app.debug = False