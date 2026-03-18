#!/usr/bin/env python3
"""
Simple web interface for Yelp configuration and monitoring
"""
from flask import Flask, render_template_string, request, jsonify, redirect
import subprocess
import os
import json
from datetime import datetime

app = Flask(__name__)

# Paths
YELP_DIR = "/home/ljung/yelp"
CONFIG_FILE = os.path.join(YELP_DIR, "yelp_complete.py")
LOG_FILE = os.path.join(YELP_DIR, "logs", "yelp.log")

# HTML Template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Yelp Control Panel</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; }
        .card { background: white; padding: 20px; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        h2 { color: #666; margin-top: 0; }
        .status { padding: 10px; border-radius: 4px; margin: 10px 0; }
        .status.running { background: #d4edda; color: #155724; }
        .status.stopped { background: #f8d7da; color: #721c24; }
        input[type="number"], input[type="text"] { padding: 8px; width: 200px; margin: 5px 0; }
        button { padding: 10px 20px; margin: 5px; cursor: pointer; border: none; border-radius: 4px; font-size: 14px; }
        .btn-primary { background: #007bff; color: white; }
        .btn-success { background: #28a745; color: white; }
        .btn-danger { background: #dc3545; color: white; }
        .btn-secondary { background: #6c757d; color: white; }
        button:hover { opacity: 0.9; }
        .log-container { background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 4px;
                         max-height: 400px; overflow-y: scroll; font-family: 'Courier New', monospace; font-size: 12px; }
        .param-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .param-item { margin: 10px 0; }
        label { display: block; font-weight: bold; margin-bottom: 5px; color: #555; }
        .help-text { font-size: 12px; color: #888; margin-top: 3px; }
        @media (max-width: 768px) {
            .param-grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎤 Yelp Control Panel</h1>

        <!-- Status Card -->
        <div class="card">
            <h2>Service Status</h2>
            <div class="status {{ status_class }}">{{ status_text }}</div>
            <button class="btn-success" onclick="serviceAction('start')">▶ Start</button>
            <button class="btn-danger" onclick="serviceAction('stop')">⏹ Stop</button>
            <button class="btn-secondary" onclick="serviceAction('restart')">🔄 Restart</button>
            <button class="btn-primary" onclick="location.reload()">↻ Refresh</button>
        </div>

        <!-- System Health Card -->
        <div class="card">
            <h2>System Health</h2>
            <div class="param-grid">
                <div class="param-item">
                    <label>🔊 Audio Output</label>
                    <div class="status {{ audio.output_class }}">{{ audio.output_status }}</div>
                    <div class="help-text">Master: {{ audio.master_volume }}</div>
                </div>
                <div class="param-item">
                    <label>🎤 PulseAudio</label>
                    <div class="status {{ audio.pulse_class }}">{{ audio.pulse_status }}</div>
                </div>
            </div>
            <button class="btn-secondary" onclick="serviceAction('fix_audio')">🔧 Fix Audio (Unmute & Restart PA)</button>
        </div>

        <!-- Configuration Card -->
        <div class="card">
            <h2>Configuration</h2>
            <form method="POST" action="/save_config">
                <div class="param-grid">
                    <div class="param-item">
                        <label>Volume Threshold (RUF_SCHWELLE)</label>
                        <input type="number" name="ruf_schwelle" step="0.0001" value="{{ config.ruf_schwelle }}" required>
                        <div class="help-text">0.0005 = current, lower = more sensitive</div>
                    </div>

                    <div class="param-item">
                        <label>Silence Duration (STILLE_DAUER)</label>
                        <input type="number" name="stille_dauer" step="0.1" value="{{ config.stille_dauer }}" required>
                        <div class="help-text">Seconds of silence after call</div>
                    </div>

                    <div class="param-item">
                        <label>Min Audio Length (MIN_AUDIO_LAENGE)</label>
                        <input type="number" name="min_audio" step="0.1" value="{{ config.min_audio }}" required>
                        <div class="help-text">Minimum recording length in seconds</div>
                    </div>

                    <div class="param-item">
                        <label>Cooldown (PAUSE_NACH_ANTWORT)</label>
                        <input type="number" name="cooldown" step="1" value="{{ config.cooldown }}" required>
                        <div class="help-text">Seconds between responses</div>
                    </div>

                    <div class="param-item">
                        <label>Speech Speed (PIPER_SPEECH_SPEED)</label>
                        <input type="number" name="speech_speed" step="0.1" value="{{ config.speech_speed }}" required>
                        <div class="help-text">1.0 = normal, 1.5 = slower</div>
                    </div>
                </div>
                <button type="submit" class="btn-primary">💾 Save Configuration</button>
            </form>
        </div>

        <!-- Logs Card -->
        <div class="card">
            <h2>Recent Logs (last 50 lines)</h2>
            <div class="log-container" id="logs">{{ logs }}</div>
            <button class="btn-primary" onclick="refreshLogs()">↻ Refresh Logs</button>
        </div>
    </div>

    <script>
        function serviceAction(action) {
            fetch('/service/' + action, { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    alert(data.message);
                    location.reload();
                })
                .catch(err => alert('Error: ' + err));
        }

        function refreshLogs() {
            fetch('/logs')
                .then(response => response.text())
                .then(data => {
                    document.getElementById('logs').innerHTML = data;
                });
        }

        // Auto-refresh logs every 10 seconds
        setInterval(refreshLogs, 10000);
    </script>
</body>
</html>
"""

def get_service_status():
    """Check if yelp is running"""
    result = subprocess.run(['pgrep', '-f', 'yelp_complete.py'], capture_output=True)
    if result.returncode == 0:
        return "running", "Service is Running"
    else:
        return "stopped", "Service is Stopped"

def get_audio_status():
    """Check audio system health"""
    status = {
        'output_status': 'Unknown',
        'output_class': 'stopped',
        'master_volume': 'Unknown',
        'pulse_status': 'Unknown',
        'pulse_class': 'stopped'
    }

    # Check Master volume
    try:
        result = subprocess.run(['amixer', 'get', 'Master'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout
            # Look for [on] or [off]
            if '[on]' in lines:
                status['output_status'] = 'Unmuted'
                status['output_class'] = 'running'
            elif '[off]' in lines:
                status['output_status'] = 'MUTED'
                status['output_class'] = 'stopped'

            # Extract volume percentage
            import re
            match = re.search(r'\[(\d+)%\]', lines)
            if match:
                status['master_volume'] = f"{match.group(1)}%"
    except:
        status['output_status'] = 'Error checking'

    # Check PulseAudio
    try:
        result = subprocess.run(['pulseaudio', '--check'], capture_output=True)
        if result.returncode == 0:
            status['pulse_status'] = 'Running'
            status['pulse_class'] = 'running'
        else:
            status['pulse_status'] = 'Not Running'
            status['pulse_class'] = 'stopped'
    except:
        status['pulse_status'] = 'Error checking'

    return status

def get_config():
    """Read current configuration from script"""
    config = {}
    try:
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                if 'RUF_SCHWELLE =' in line and not line.strip().startswith('#'):
                    config['ruf_schwelle'] = float(line.split('=')[1].split('#')[0].strip())
                elif 'STILLE_DAUER =' in line and not line.strip().startswith('#'):
                    config['stille_dauer'] = float(line.split('=')[1].split('#')[0].strip())
                elif 'MIN_AUDIO_LAENGE =' in line and not line.strip().startswith('#'):
                    config['min_audio'] = float(line.split('=')[1].split('#')[0].strip())
                elif 'PAUSE_NACH_ANTWORT =' in line and not line.strip().startswith('#'):
                    config['cooldown'] = int(line.split('=')[1].split('#')[0].strip())
                elif 'PIPER_SPEECH_SPEED =' in line and not line.strip().startswith('#'):
                    config['speech_speed'] = float(line.split('=')[1].split('#')[0].strip())
    except Exception as e:
        print(f"Error reading config: {e}")

    # Defaults if not found
    config.setdefault('ruf_schwelle', 0.0005)
    config.setdefault('stille_dauer', 1.0)
    config.setdefault('min_audio', 0.1)
    config.setdefault('cooldown', 5)
    config.setdefault('speech_speed', 1.5)

    return config

def save_config(new_config):
    """Update configuration in script"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            lines = f.readlines()

        with open(CONFIG_FILE, 'w') as f:
            for line in lines:
                if 'RUF_SCHWELLE =' in line and not line.strip().startswith('#'):
                    indent = len(line) - len(line.lstrip())
                    f.write(' ' * indent + f'RUF_SCHWELLE = {new_config["ruf_schwelle"]}         # Lautstärke-Schwelle - lowered for Jabra room mic\n')
                elif 'STILLE_DAUER =' in line and not line.strip().startswith('#'):
                    indent = len(line) - len(line.lstrip())
                    f.write(' ' * indent + f'STILLE_DAUER = {new_config["stille_dauer"]}            # Sekunden Stille nach Ruf (0.5-2.0)\n')
                elif 'MIN_AUDIO_LAENGE =' in line and not line.strip().startswith('#'):
                    indent = len(line) - len(line.lstrip())
                    f.write(' ' * indent + f'MIN_AUDIO_LAENGE = {new_config["min_audio"]}        # Minimale Audio-Länge in Sekunden (verhindert zu kurze Aufnahmen)\n')
                elif 'PAUSE_NACH_ANTWORT =' in line and not line.strip().startswith('#'):
                    indent = len(line) - len(line.lstrip())
                    f.write(' ' * indent + f'PAUSE_NACH_ANTWORT = {new_config["cooldown"]}        # Cooldown zwischen Antworten in Sekunden\n')
                elif 'PIPER_SPEECH_SPEED =' in line and not line.strip().startswith('#'):
                    indent = len(line) - len(line.lstrip())
                    f.write(' ' * indent + f'PIPER_SPEECH_SPEED = {new_config["speech_speed"]}  # 1.0=normal, 1.5=slower, 2.0=very slow\n')
                else:
                    f.write(line)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def get_logs():
    """Read last 50 lines of log file"""
    try:
        result = subprocess.run(['tail', '-n', '50', LOG_FILE], capture_output=True, text=True)
        return result.stdout.replace('\n', '<br>').replace(' ', '&nbsp;')
    except Exception as e:
        return f"Error reading logs: {e}"

@app.route('/')
def index():
    status_class, status_text = get_service_status()
    config = get_config()
    logs = get_logs()
    audio = get_audio_status()

    return render_template_string(
        HTML_TEMPLATE,
        status_class=status_class,
        status_text=status_text,
        config=config,
        logs=logs,
        audio=audio
    )

@app.route('/service/<action>', methods=['POST'])
def service_control(action):
    try:
        if action == 'start':
            subprocess.Popen(['bash', os.path.join(YELP_DIR, 'start_yelp_exclusive.sh')])
            return jsonify({'status': 'success', 'message': 'Service started'})
        elif action == 'stop':
            subprocess.run(['pkill', '-f', 'yelp_complete.py'])
            return jsonify({'status': 'success', 'message': 'Service stopped'})
        elif action == 'restart':
            subprocess.run(['pkill', '-f', 'yelp_complete.py'])
            subprocess.Popen(['bash', os.path.join(YELP_DIR, 'start_yelp_exclusive.sh')])
            return jsonify({'status': 'success', 'message': 'Service restarted'})
        elif action == 'fix_audio':
            # Unmute audio
            subprocess.run(['amixer', 'set', 'Master', '100%', 'unmute'])
            subprocess.run(['amixer', 'set', 'PCM', '100%', 'unmute'])
            # Restart PulseAudio
            subprocess.run(['pulseaudio', '-k'])
            subprocess.run(['pulseaudio', '--start'])
            # Wait and restart service
            import time
            time.sleep(2)
            subprocess.run(['pkill', '-f', 'yelp_complete.py'])
            subprocess.Popen(['bash', os.path.join(YELP_DIR, 'start_yelp_exclusive.sh')])
            return jsonify({'status': 'success', 'message': 'Audio fixed and service restarted'})
        else:
            return jsonify({'status': 'error', 'message': 'Invalid action'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/save_config', methods=['POST'])
def save_configuration():
    try:
        new_config = {
            'ruf_schwelle': float(request.form['ruf_schwelle']),
            'stille_dauer': float(request.form['stille_dauer']),
            'min_audio': float(request.form['min_audio']),
            'cooldown': int(request.form['cooldown']),
            'speech_speed': float(request.form['speech_speed'])
        }

        if save_config(new_config):
            return redirect('/')
        else:
            return "Error saving configuration", 500
    except Exception as e:
        return f"Error: {e}", 500

@app.route('/logs')
def logs_only():
    return get_logs()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
