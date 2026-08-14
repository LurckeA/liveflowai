# src/liveflowai/output/iem_manager.py
from typing import Dict, List, Any

class IEMManager:
    """Manages In-Ear Monitor (IEM) transitions and audio routing"""
    
    def __init__(self):
        self.active_transitions = []
        self.iem_channels = {}
        
    def send_transition(self, transition: Dict[str, Any]) -> bool:
        """Send transition data to IEM system"""
        try:
            self.active_transitions.append(transition)
            print(f"IEM Transition sent: {transition}")
            return True
        except Exception as e:
            print(f"Error sending IEM transition: {e}")
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current IEM status"""
        return {
            'active_transitions': len(self.active_transitions),
            'channels': self.iem_channels
        }