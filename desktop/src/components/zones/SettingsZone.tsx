/**
 * Settings Zone - Configuration Panel
 * Local/Cloud toggle, Model selection, Ollama controls
 */

import React, { useState, useEffect } from 'react';
import { View, Text, StyleSheet, Switch } from 'react-native';
import { useUIStore } from '../../store/uiStore';
import { listen } from '@tauri-apps/api/event';
import { invoke } from '@tauri-apps/api/tauri';
import { OllamaDownloadModal, OllamaProgress } from './modal/OllamaDownloadModal';

export const SettingsZone: React.FC = () => {
  const [localMode, setLocalMode] = useState(false);
  const [showOllamaModal, setShowOllamaModal] = useState(false);
  const [progress, setProgress] = useState<OllamaProgress>({
    status: 'idle',
    progress: 0,
  });

  // Listen for Tauri IPC events for Ollama progress
  useEffect(() => {
    const unlisten = listen<OllamaProgress>('ollama-download-progress', (event) => {
      setProgress(event.payload);
    });

    return () => {
      unlisten.then(fn => fn());
    };
  }, []);

  // Check Ollama status on mount
  useEffect(() => {
    const checkOllama = async () => {
      try {
        const available = await invoke<string>('check_ollama');
        setLocalMode(available === 'available');
      } catch (e) {
        setLocalMode(false);
      }
    };
    checkOllama();
  }, []);

  const handleLocalToggle = async (value: boolean) => {
    if (value) {
      // User wants Local mode
      if (progress.status === 'idle') {
        // Check if Ollama is installed
        try {
          await invoke('install_ollama');
          setShowOllamaModal(true);
        } catch (e) {
          console.error('Failed to install Ollama:', e);
        }
      } else if (progress.status === 'complete') {
        // Already downloaded, switch immediately
        setLocalMode(true);
      } else {
        // Already downloading, show modal
        setShowOllamaModal(true);
      }
    } else {
      // Switch to Cloud mode
      setLocalMode(false);
    }
  };

  const handleOllamaDownload = async () => {
    try {
      await invoke('install_ollama');
      setShowOllamaModal(true);
    } catch (e) {
      console.error('Failed to start download:', e);
    }
  };

  const handleSwitchToLocal = async () => {
    setLocalMode(true);
    setShowOllamaModal(false);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Settings</Text>
      <Text style={styles.subtitle}>Configure XenoSys</Text>

      {/* Mode Toggle */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>EXECUTION MODE</Text>
        <View style={styles.toggleCard}>
          <View style={styles.toggleHeader}>
            <View>
              <Text style={styles.toggleLabel}>Local Mode</Text>
              <Text style={styles.toggleDescription}>
                Run inference on this machine
              </Text>
            </View>
            <Switch
              value={localMode}
              onValueChange={handleLocalToggle}
              trackColor={{ false: '#333', true: '#00FF9D50' }}
              thumbColor={localMode ? '#00FF9D' : '#666'}
            />
          </View>
          
          {/* Model Info */}
          {localMode && (
            <View style={styles.modelInfo}>
              <Text style={styles.modelLabel}>Model</Text>
              <Text style={styles.modelValue}>llama3.1:8b</Text>
            </View>
          )}

          {/* Download Button */}
          {!localMode && progress.status !== 'complete' && (
            <button 
              style={styles.downloadButton}
              onClick={handleOllamaDownload}
            >
              <Text style={styles.downloadText}>Download Model</Text>
            </button>
          )}
        </View>
      </View>

      {/* Cloud Settings */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>CLOUD PROVIDER</Text>
        <View style={styles.card}>
          <View style={styles.cardRow}>
            <Text style={styles.cardLabel}>Provider</Text>
            <Text style={styles.cardValue}>OpenAI</Text>
          </View>
          <View style={styles.cardRow}>
            <Text style={styles.cardLabel}>Model</Text>
            <Text style={styles.cardValue}>gpt-4o</Text>
          </View>
          <View style={styles.cardRow}>
            <Text style={styles.cardLabel}>API Key</Text>
            <Text style={styles.cardValue}>••••••••</Text>
          </View>
        </View>
      </View>

      {/* About */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>ABOUT</Text>
        <View style={styles.card}>
          <View style={styles.cardRow}>
            <Text style={styles.cardLabel}>Version</Text>
            <Text style={styles.cardValue}>1.0.0</Text>
          </View>
          <View style={styles.cardRow}>
            <Text style={styles.cardLabel}>License</Text>
            <Text style={styles.cardValue}>MIT</Text>
          </View>
        </View>
      </View>

      {/* Ollama Modal */}
      <OllamaDownloadModal
        visible={showOllamaModal}
        onClose={() => setShowOllamaModal(false)}
        onMinimize={() => setShowOllamaModal(false)}
        progress={progress}
        onSwitchMode={handleSwitchToLocal}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 20,
    backgroundColor: '#0A0A0A',
  },
  title: {
    color: '#00FF9D',
    fontSize: 24,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  subtitle: {
    color: '#666',
    fontSize: 14,
    marginBottom: 24,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    color: '#00B8FF',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 12,
  },
  toggleCard: {
    backgroundColor: '#121212',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  toggleHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  toggleLabel: {
    color: '#E0E0E0',
    fontSize: 16,
    fontWeight: '600',
  },
  toggleDescription: {
    color: '#666',
    fontSize: 13,
    marginTop: 2,
  },
  modelInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: '#2A2A2A',
  },
  modelLabel: { color: '#666', fontSize: 14 },
  modelValue: { color: '#00FF9D', fontSize: 14 },
  downloadButton: {
    marginTop: 12,
    paddingVertical: 10,
    backgroundColor: '#00B8FF20',
    borderRadius: 8,
    alignItems: 'center',
  },
  downloadText: { color: '#00B8FF', fontSize: 14, fontWeight: '600' },
  card: {
    backgroundColor: '#121212',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  cardRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  cardLabel: { color: '#666', fontSize: 14 },
  cardValue: { color: '#E0E0E0', fontSize: 14 },
});

export default SettingsZone;