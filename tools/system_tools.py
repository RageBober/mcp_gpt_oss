# Дополнительные системные инструменты для MCP сервера
import os
import json
import subprocess
import psutil
import time
from datetime import datetime
from typing import Dict, List, Any

class SystemTools:
    """Коллекция дополнительных системных инструментов"""
    
    def __init__(self, mcp_server):
        self.mcp_server = mcp_server
        self.register_tools()
    
    def register_tools(self):
        """Регистрация дополнительных инструментов в MCP сервере"""
        # Здесь можно добавить регистрацию через декораторы
        # когда основной сервер будет поддерживать это
        pass
    
    async def get_network_info(self) -> str:
        """Получение информации о сетевых подключениях"""
        try:
            connections = psutil.net_connections(kind='inet')
            network_info = {
                "active_connections": len(connections),
                "listening_ports": [],
                "established_connections": []
            }
            
            for conn in connections[:20]:  # Ограничиваем количество
                if conn.status == 'LISTEN':
                    network_info["listening_ports"].append({
                        "port": conn.laddr.port,
                        "address": conn.laddr.ip
                    })
                elif conn.status == 'ESTABLISHED':
                    network_info["established_connections"].append({
                        "local": f"{conn.laddr.ip}:{conn.laddr.port}",
                        "remote": f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "Unknown"
                    })
            
            return json.dumps(network_info, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def get_system_services(self) -> str:
        """Получение списка системных служб (Windows)"""
        try:
            if os.name != 'nt':
                return json.dumps({"error": "This feature is only available on Windows"})
            
            result = subprocess.run(
                'sc query type= service state= all',
                capture_output=True, text=True, shell=True, timeout=30
            )
            
            if result.returncode == 0:
                # Простейший парсинг вывода sc query
                services = []
                lines = result.stdout.split('\n')
                current_service = {}
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('SERVICE_NAME:'):
                        if current_service:
                            services.append(current_service)
                        current_service = {"name": line.split(':', 1)[1].strip()}
                    elif line.startswith('DISPLAY_NAME:'):
                        current_service["display_name"] = line.split(':', 1)[1].strip()
                    elif line.startswith('STATE'):
                        current_service["state"] = line.split(':', 1)[1].strip()
                
                if current_service:
                    services.append(current_service)
                
                return json.dumps(services[:50], indent=2)  # Ограничиваем до 50 служб
            else:
                return json.dumps({"error": "Failed to get services", "stderr": result.stderr})
                
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def get_disk_usage(self) -> str:
        """Детальная информация об использовании дисков"""
        try:
            disk_info = []
            
            # Получение всех дисков
            partitions = psutil.disk_partitions()
            
            for partition in partitions:
                try:
                    partition_usage = psutil.disk_usage(partition.mountpoint)
                    disk_info.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "total_gb": round(partition_usage.total / (1024**3), 2),
                        "used_gb": round(partition_usage.used / (1024**3), 2),
                        "free_gb": round(partition_usage.free / (1024**3), 2),
                        "percent_used": round((partition_usage.used / partition_usage.total) * 100, 1)
                    })
                except PermissionError:
                    # Некоторые диски могут быть недоступны
                    disk_info.append({
                        "device": partition.device,
                        "mountpoint": partition.mountpoint,
                        "fstype": partition.fstype,
                        "status": "Access Denied"
                    })
            
            return json.dumps(disk_info, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def get_startup_programs(self) -> str:
        """Получение списка программ автозапуска (Windows)"""
        try:
            if os.name != 'nt':
                return json.dumps({"error": "This feature is only available on Windows"})
            
            startup_programs = []
            
            # Проверка реестра для программ автозапуска
            registry_paths = [
                r'SOFTWARE\Microsoft\Windows\CurrentVersion\Run',
                r'SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce'
            ]
            
            for reg_path in registry_paths:
                try:
                    result = subprocess.run(
                        f'reg query "HKLM\\{reg_path}"',
                        capture_output=True, text=True, shell=True, timeout=10
                    )
                    
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        for line in lines:
                            if 'REG_SZ' in line or 'REG_EXPAND_SZ' in line:
                                parts = line.strip().split(None, 2)
                                if len(parts) >= 3:
                                    startup_programs.append({
                                        "name": parts[0],
                                        "command": parts[2],
                                        "registry_path": reg_path
                                    })
                except:
                    continue
            
            return json.dumps(startup_programs, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def cleanup_temp_files(self) -> str:
        """Очистка временных файлов"""
        try:
            if not self.mcp_server.unrestricted_access:
                return json.dumps({
                    "error": "Administrative privileges required",
                    "message": "Enable unrestricted access to perform cleanup operations"
                })
            
            cleaned_files = 0
            freed_space = 0
            
            temp_paths = []
            if os.name == 'nt':
                temp_paths = [
                    os.path.expandvars(r'%TEMP%'),
                    os.path.expandvars(r'%WINDIR%\Temp'),
                    os.path.expandvars(r'%LOCALAPPDATA%\Temp')
                ]
            else:
                temp_paths = ['/tmp', '/var/tmp']
            
            for temp_path in temp_paths:
                if os.path.exists(temp_path):
                    try:
                        for root, dirs, files in os.walk(temp_path):
                            for file in files:
                                file_path = os.path.join(root, file)
                                try:
                                    # Удаляем только файлы старше 7 дней
                                    if os.path.getmtime(file_path) < time.time() - (7 * 24 * 3600):
                                        file_size = os.path.getsize(file_path)
                                        os.remove(file_path)
                                        cleaned_files += 1
                                        freed_space += file_size
                                except (PermissionError, FileNotFoundError):
                                    continue
                    except Exception:
                        continue
            
            return json.dumps({
                "success": True,
                "cleaned_files": cleaned_files,
                "freed_space_mb": round(freed_space / (1024*1024), 2),
                "message": f"Cleaned {cleaned_files} files, freed {freed_space // (1024*1024)} MB"
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def get_system_temperatures(self) -> str:
        """Получение температур системы (если доступно)"""
        try:
            temps = psutil.sensors_temperatures()
            if not temps:
                return json.dumps({"message": "No temperature sensors found"})
            
            temperature_data = {}
            for name, entries in temps.items():
                temperature_data[name] = []
                for entry in entries:
                    temperature_data[name].append({
                        "label": entry.label or "Unknown",
                        "current": entry.current,
                        "high": entry.high,
                        "critical": entry.critical
                    })
            
            return json.dumps(temperature_data, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def optimize_system_performance(self) -> str:
        """Комплексная оптимизация производительности системы"""
        try:
            if not self.mcp_server.unrestricted_access:
                return json.dumps({
                    "error": "Administrative privileges required",
                    "message": "Enable unrestricted access to perform system optimization"
                })
            
            optimizations = []
            
            # 1. Очистка DNS кэша
            if os.name == 'nt':
                try:
                    result = subprocess.run(
                        'ipconfig /flushdns',
                        capture_output=True, text=True, shell=True, timeout=30
                    )
                    if result.returncode == 0:
                        optimizations.append("DNS cache flushed")
                except:
                    pass
            
            # 2. Очистка временных файлов (вызов предыдущего метода)
            temp_cleanup = await self.cleanup_temp_files()
            temp_result = json.loads(temp_cleanup)
            if temp_result.get("success"):
                optimizations.append(f"Temporary files cleaned: {temp_result.get('cleaned_files', 0)} files")
            
            # 3. Оптимизация приоритетов процессов с высоким CPU
            try:
                high_cpu_processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                    if proc.info['cpu_percent'] and proc.info['cpu_percent'] > 80:
                        high_cpu_processes.append(proc.info)
                
                if high_cpu_processes:
                    optimizations.append(f"Found {len(high_cpu_processes)} high CPU processes")
            except:
                pass
            
            # 4. Проверка свободного места на диске
            try:
                disk_usage = psutil.disk_usage('C:' if os.name == 'nt' else '/')
                free_space_percent = (disk_usage.free / disk_usage.total) * 100
                
                if free_space_percent < 10:
                    optimizations.append("WARNING: Low disk space detected")
                else:
                    optimizations.append("Disk space is adequate")
            except:
                pass
            
            return json.dumps({
                "success": True,
                "optimizations_performed": optimizations,
                "timestamp": datetime.now().isoformat(),
                "message": "System optimization completed"
            })
        except Exception as e:
            return json.dumps({"error": str(e)})


class AutonomousTaskManager:
    """Менеджер автономных задач с расширенной функциональностью"""
    
    def __init__(self, mcp_server):
        self.mcp_server = mcp_server
        self.recurring_tasks = {}
    
    async def create_scheduled_task(self, task_description: str, schedule_type: str, interval: int) -> str:
        """Создание задачи по расписанию"""
        try:
            task_id = f"scheduled_{int(time.time())}_{hash(task_description) % 10000}"
            
            task_data = {
                "id": task_id,
                "description": task_description,
                "schedule_type": schedule_type,  # 'interval', 'daily', 'weekly'
                "interval": interval,
                "next_run": time.time() + interval,
                "created": datetime.now().isoformat(),
                "status": "scheduled"
            }
            
            self.recurring_tasks[task_id] = task_data
            
            return json.dumps({
                "success": True,
                "task_id": task_id,
                "message": f"Scheduled task created: {task_description}",
                "next_run": datetime.fromtimestamp(task_data["next_run"]).isoformat()
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    async def get_scheduled_tasks(self) -> str:
        """Получение списка запланированных задач"""
        try:
            current_time = time.time()
            tasks_info = []
            
            for task_id, task_data in self.recurring_tasks.items():
                time_until_next = task_data["next_run"] - current_time
                tasks_info.append({
                    "id": task_id,
                    "description": task_data["description"],
                    "status": task_data["status"],
                    "time_until_next_run_minutes": round(time_until_next / 60, 1),
                    "created": task_data["created"]
                })
            
            return json.dumps(tasks_info, indent=2)
        except Exception as e:
            return json.dumps({"error": str(e)})


# Функция интеграции с основным сервером
def register_additional_tools(mcp_server):
    """Регистрация дополнительных инструментов в основном сервере"""
    system_tools = SystemTools(mcp_server)
    task_manager = AutonomousTaskManager(mcp_server)
    
    # Здесь можно добавить логику регистрации инструментов
    # когда основной сервер будет поддерживать динамическую регистрацию
    
    return system_tools, task_manager
