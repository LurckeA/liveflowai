# src/liveflowai/detection/song_predictor.py
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import numpy as np
import joblib
from pathlib import Path

class SongPredictor:
    def __init__(self):
        self.model = RandomForestClassifier(n_estimators=100)
        self.scaler = StandardScaler()
        self.trained = False
        
    def train(self, song_features: dict):
        """Train predictor on song library"""
        X = []
        y = []
        
        for song_name, features in song_features.items():
            # Extract features for training
            X.append(self.extract_training_features(features))
            y.append(song_name)
        
        X = np.array(X)
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        self.trained = True
        
    def predict(self, chord_progression: np.ndarray) -> str:
        """Predict next song from chord progression"""
        if not self.trained:
            return None
            
        features = self.extract_prediction_features(chord_progression)
        features_scaled = self.scaler.transform([features])
        return self.model.predict(features_scaled)[0]
    
    def extract_training_features(self, song_features: dict) -> np.ndarray:
        """Extract features for training"""
        return np.array([
            song_features['tempo'],
            self.chord_to_numeric(song_features['chord_progression'][:10]),
            song_features['energy'],
            # Add more features
        ])
    
    def chord_to_numeric(self, chords: list) -> float:
        """Convert chord progression to numeric representation"""
        # Simple encoding
        chord_map = {'C': 0, 'D': 2, 'E': 4, 'F': 5, 'G': 7, 'A': 9, 'B': 11}
        return sum([chord_map.get(c[0], 0) for c in chords[:10]]) / 10