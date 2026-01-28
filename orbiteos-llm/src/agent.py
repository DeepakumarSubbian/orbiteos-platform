#!/usr/bin/env python3
"""
OrbitEOS LLM Agent
Chat interface for energy system management using Ollama.

Features:
- Ollama integration (llama3.1:8b)
- Chat interface on port 9000
- Query system status via OpenEMS API
- Energy optimization suggestions
- Natural language interaction
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("orbiteos-llm")

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
ORBITEOS_API_URL = os.getenv("ORBITEOS_API_URL", "http://orbiteos-api:8000")
OPENEMS_API_URL = os.getenv("OPENEMS_API_URL", "http://openems-edge:8084")
OPENEMS_USER = os.getenv("OPENEMS_USER", "admin")
OPENEMS_PASSWORD = os.getenv("OPENEMS_PASSWORD", "admin")

# System prompt for energy assistant
SYSTEM_PROMPT = """You are OrbitEOS, an intelligent energy management assistant. You help users understand and optimize their home energy system.

You have access to real-time data from:
- Solar PV system (production, sun position)
- Battery storage (SOC, charge/discharge power)
- Grid connection (import/export)
- EV charger (charging status, vehicle SOC)

When answering questions:
1. Use the actual data provided in the context
2. Give specific numbers and recommendations
3. Explain energy flows clearly
4. Suggest optimizations based on current conditions
5. Be conversational but informative

Current system data will be provided before each query. Use this data to give accurate, helpful responses."""


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None


class ChatResponse(BaseModel):
    response: str
    system_data: Optional[Dict[str, Any]] = None


class EnergyAgent:
    """LLM-powered energy management agent."""

    def __init__(self):
        self.http_client = httpx.AsyncClient(timeout=60.0)
        self.conversation_history: List[Dict[str, str]] = []

    async def get_openems_data(self) -> Dict[str, Any]:
        """Fetch current data from OpenEMS Edge."""
        try:
            # Get channel data from OpenEMS REST API with authentication
            auth = httpx.BasicAuth(OPENEMS_USER, OPENEMS_PASSWORD)

            # Fetch individual channels since wildcard may not work
            channels = {
                'EssSoc': '_sum/EssSoc',
                'EssActivePower': '_sum/EssActivePower',
                'ProductionActivePower': '_sum/ProductionActivePower',
                'ConsumptionActivePower': '_sum/ConsumptionActivePower',
                'GridActivePower': '_sum/GridActivePower'
            }

            data = {}
            for key, channel in channels.items():
                try:
                    response = await self.http_client.get(
                        f"{OPENEMS_API_URL}/rest/channel/{channel}",
                        auth=auth,
                        timeout=5.0
                    )
                    if response.status_code == 200:
                        result = response.json()
                        data[key] = {'value': result.get('value')}
                except Exception:
                    data[key] = {'value': None}

            if data.get('EssSoc', {}).get('value') is not None:
                return self._parse_openems_data(data)

        except Exception as e:
            logger.warning(f"Failed to fetch OpenEMS data: {e}")

        # Return simulated data if OpenEMS unavailable
        return self._get_simulated_data()

    def _parse_openems_data(self, raw_data: Dict) -> Dict[str, Any]:
        """Parse OpenEMS channel data into friendly format."""
        def get_value(key: str, default=0):
            val = raw_data.get(key, {}).get('value')
            return val if val is not None else default

        solar_power = get_value('ProductionActivePower', 0)
        grid_power = get_value('GridActivePower', 0)
        consumption = get_value('ConsumptionActivePower', 0)
        battery_soc = get_value('EssSoc', 50)
        battery_power = get_value('EssActivePower', 0)

        return {
            'timestamp': datetime.now().isoformat(),
            'solar': {
                'power_w': solar_power,
                'power_kw': round(solar_power / 1000, 2) if solar_power else 0,
                'status': 'producing' if solar_power and solar_power > 100 else 'idle'
            },
            'battery': {
                'soc_percent': battery_soc,
                'power_w': battery_power,
                'power_kw': round(battery_power / 1000, 2) if battery_power else 0,
                'status': 'charging' if battery_power and battery_power < -50 else ('discharging' if battery_power and battery_power > 50 else 'standby')
            },
            'grid': {
                'power_w': grid_power,
                'power_kw': round(grid_power / 1000, 2) if grid_power else 0,
                'status': 'importing' if grid_power and grid_power > 50 else ('exporting' if grid_power and grid_power < -50 else 'balanced')
            },
            'home': {
                'consumption_w': consumption,
                'consumption_kw': round(consumption / 1000, 2) if consumption else 0
            },
            'source': 'openems'
        }

    def _get_simulated_data(self) -> Dict[str, Any]:
        """Get simulated data when OpenEMS is unavailable."""
        hour = datetime.now().hour

        # Simulate solar based on time of day
        if 6 <= hour <= 18:
            solar_factor = 1 - abs(hour - 12) / 6
            solar_power = int(3000 * solar_factor * 1.2)  # Peak ~3.6kW
        else:
            solar_power = 0

        # Simulate battery (charging during day, discharging at night)
        if solar_power > 1500:
            battery_power = -min(solar_power - 1000, 2000)  # Charging
            battery_soc = 60 + (hour - 6) * 3
        else:
            battery_power = 800  # Discharging
            battery_soc = max(20, 90 - (hour - 18) * 5) if hour >= 18 else 50

        consumption = 1200 + (300 if 17 <= hour <= 21 else 0)
        grid_power = consumption - solar_power - battery_power

        return {
            'timestamp': datetime.now().isoformat(),
            'solar': {
                'power_w': solar_power,
                'power_kw': round(solar_power / 1000, 2),
                'status': 'producing' if solar_power > 100 else 'idle'
            },
            'battery': {
                'soc_percent': min(100, max(10, battery_soc)),
                'power_w': battery_power,
                'power_kw': round(battery_power / 1000, 2),
                'status': 'charging' if battery_power < -50 else ('discharging' if battery_power > 50 else 'standby')
            },
            'grid': {
                'power_w': grid_power,
                'power_kw': round(grid_power / 1000, 2),
                'status': 'importing' if grid_power > 50 else ('exporting' if grid_power < -50 else 'balanced')
            },
            'home': {
                'consumption_w': consumption,
                'consumption_kw': round(consumption / 1000, 2)
            },
            'note': 'Simulated data - OpenEMS connection unavailable'
        }

    async def generate_response(self, user_message: str, history: List[ChatMessage] = None) -> str:
        """Generate response using Ollama."""
        # Get current system data
        system_data = await self.get_openems_data()

        # Build context with system data
        context = f"""Current Energy System Status ({system_data['timestamp']}):

Solar PV:
- Power: {system_data['solar']['power_kw']} kW
- Status: {system_data['solar']['status']}

Battery Storage:
- SOC: {system_data['battery']['soc_percent']}%
- Power: {system_data['battery']['power_kw']} kW ({system_data['battery']['status']})

Grid Connection:
- Power: {system_data['grid']['power_kw']} kW ({system_data['grid']['status']})

Home Consumption:
- Power: {system_data['home']['consumption_kw']} kW
"""

        # Build messages for Ollama
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": context}
        ]

        # Add conversation history
        if history:
            for msg in history[-6:]:  # Keep last 6 messages for context
                messages.append({"role": msg.role, "content": msg.content})

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        try:
            # Call Ollama API
            response = await self.http_client.post(
                f"{OLLAMA_HOST}/api/chat",
                json={
                    "model": OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 500
                    }
                },
                timeout=60.0
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('message', {}).get('content', 'I apologize, but I could not generate a response.')
            else:
                logger.error(f"Ollama error: {response.status_code} - {response.text}")
                return self._get_fallback_response(user_message, system_data)

        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return self._get_fallback_response(user_message, system_data)

    def _get_fallback_response(self, query: str, data: Dict) -> str:
        """Generate fallback response without LLM."""
        query_lower = query.lower()

        if 'solar' in query_lower or 'production' in query_lower:
            return f"Currently producing {data['solar']['power_kw']} kW from solar. Status: {data['solar']['status']}."

        elif 'battery' in query_lower or 'soc' in query_lower:
            return f"Battery is at {data['battery']['soc_percent']}% SOC, {data['battery']['status']} at {abs(data['battery']['power_kw'])} kW."

        elif 'grid' in query_lower:
            action = "importing from" if data['grid']['power_w'] > 0 else "exporting to"
            return f"Currently {action} the grid at {abs(data['grid']['power_kw'])} kW."

        elif 'consumption' in query_lower or 'using' in query_lower:
            return f"Home consumption is {data['home']['consumption_kw']} kW."

        elif 'status' in query_lower or 'overview' in query_lower:
            return f"""System Overview:
- Solar: {data['solar']['power_kw']} kW ({data['solar']['status']})
- Battery: {data['battery']['soc_percent']}% ({data['battery']['status']})
- Grid: {data['grid']['power_kw']} kW ({data['grid']['status']})
- Consumption: {data['home']['consumption_kw']} kW"""

        else:
            return "I can help you with solar production, battery status, grid power, and energy optimization. What would you like to know?"


# FastAPI Application
app = FastAPI(
    title="OrbitEOS LLM Agent",
    description="Intelligent Energy Management Chat Interface",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global agent instance
agent = EnergyAgent()


@app.get("/", response_class=HTMLResponse)
async def chat_ui():
    """Serve chat interface."""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>OrbitEOS Energy Assistant</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a0a; color: #fff; height: 100vh; display: flex; flex-direction: column; }
        .header { background: linear-gradient(135deg, #00A86B, #0066CC); padding: 20px; text-align: center; }
        .header h1 { font-size: 24px; margin-bottom: 5px; }
        .header p { opacity: 0.8; font-size: 14px; }
        .chat-container { flex: 1; overflow-y: auto; padding: 20px; }
        .message { margin-bottom: 15px; display: flex; }
        .message.user { justify-content: flex-end; }
        .message-content { max-width: 80%; padding: 12px 16px; border-radius: 18px; line-height: 1.4; }
        .message.user .message-content { background: #0066CC; }
        .message.assistant .message-content { background: #1a1a1a; border: 1px solid #333; }
        .input-container { padding: 20px; background: #111; border-top: 1px solid #222; display: flex; gap: 10px; }
        input { flex: 1; padding: 14px 18px; border: 1px solid #333; border-radius: 24px; background: #1a1a1a; color: #fff; font-size: 16px; outline: none; }
        input:focus { border-color: #00A86B; }
        button { padding: 14px 28px; background: #00A86B; border: none; border-radius: 24px; color: #fff; font-size: 16px; cursor: pointer; font-weight: 600; }
        button:hover { background: #00c77b; }
        button:disabled { background: #333; cursor: not-allowed; }
        .typing { display: flex; gap: 4px; padding: 12px 16px; }
        .typing span { width: 8px; height: 8px; background: #666; border-radius: 50%; animation: typing 1s infinite; }
        .typing span:nth-child(2) { animation-delay: 0.2s; }
        .typing span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typing { 0%, 100% { opacity: 0.3; } 50% { opacity: 1; } }
        .status { font-size: 12px; color: #666; padding: 10px 20px; text-align: center; }
    </style>
</head>
<body>
    <div class="header">
        <h1>OrbitEOS Energy Assistant</h1>
        <p>Ask me about your solar, battery, and energy usage</p>
    </div>
    <div class="chat-container" id="chat"></div>
    <div class="status" id="status">Connected to OpenEMS</div>
    <div class="input-container">
        <input type="text" id="input" placeholder="Ask about your energy system..." onkeypress="if(event.key==='Enter')sendMessage()">
        <button onclick="sendMessage()" id="sendBtn">Send</button>
    </div>
    <script>
        const chat = document.getElementById('chat');
        const input = document.getElementById('input');
        const sendBtn = document.getElementById('sendBtn');
        let history = [];

        function addMessage(content, isUser) {
            const div = document.createElement('div');
            div.className = 'message ' + (isUser ? 'user' : 'assistant');
            div.innerHTML = '<div class="message-content">' + content.replace(/\\n/g, '<br>') + '</div>';
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        function showTyping() {
            const div = document.createElement('div');
            div.className = 'message assistant';
            div.id = 'typing';
            div.innerHTML = '<div class="typing"><span></span><span></span><span></span></div>';
            chat.appendChild(div);
            chat.scrollTop = chat.scrollHeight;
        }

        function hideTyping() {
            const typing = document.getElementById('typing');
            if (typing) typing.remove();
        }

        async function sendMessage() {
            const message = input.value.trim();
            if (!message) return;

            input.value = '';
            sendBtn.disabled = true;
            addMessage(message, true);
            history.push({role: 'user', content: message});
            showTyping();

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message, history})
                });
                const data = await response.json();
                hideTyping();
                addMessage(data.response, false);
                history.push({role: 'assistant', content: data.response});
            } catch (e) {
                hideTyping();
                addMessage('Sorry, I encountered an error. Please try again.', false);
            }
            sendBtn.disabled = false;
            input.focus();
        }

        // Welcome message
        addMessage("Hello! I'm your OrbitEOS energy assistant. I can help you understand your solar production, battery status, grid usage, and suggest ways to optimize your energy. What would you like to know?", false);
    </script>
</body>
</html>
"""


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handle chat requests."""
    response = await agent.generate_response(
        request.message,
        request.history
    )
    system_data = await agent.get_openems_data()
    return ChatResponse(response=response, system_data=system_data)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "model": OLLAMA_MODEL}


@app.get("/api/status")
async def get_status():
    """Get current system status."""
    return await agent.get_openems_data()


if __name__ == "__main__":
    port = int(os.getenv('PORT', 9000))
    uvicorn.run(
        "agent:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
