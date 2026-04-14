/**
 * Pairing Screen - QR Code Pairing
 * Scan QR code from Desktop to connect
 */

import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Alert, CameraView, useCameraPermissions } from 'react-native';
import { useTunnelHealth } from '../hooks/useTunnelHealth';

// Simulated QR code data structure
interface QRData {
  tunnelUrl: string;
  token: string;
}

export const PairingScreen = () => {
  const [mode, setMode] = useState<'welcome' | 'scan' | 'manual'>('welcome');
  const [manualUrl, setManualUrl] = useState('');
  const [manualToken, setManualToken] = useState('');
  const { pair, isLoading, error } = useTunnelHealth();
  const [permission, requestPermission] = useCameraPermissions();

  const handleManualPair = async () => {
    if (!manualUrl || !manualToken) {
      Alert.alert('Missing Info', 'Please enter both Tunnel URL and Token');
      return;
    }
    
    Alert.alert(
      'Confirm Pairing',
      `Connect to ${manualUrl}?`,
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Connect', 
          onPress: async () => {
            const success = await pair(manualUrl, manualToken);
            if (!success) {
              Alert.alert('Connection Failed', error || 'Could not connect to server');
            }
          }
        },
      ]
    );
  };

  const handleScanQR = async (data: QRData) => {
    const success = await pair(data.tunnelUrl, data.token);
    if (!success) {
      Alert.alert('Pairing Failed', 'Could not connect. Please try again.');
    }
  };

  // Welcome Screen
  if (mode === 'welcome') {
    return (
      <View style={styles.container}>
        <View style={styles.content}>
          <Text style={styles.logo}>⚡</Text>
          <Text style={styles.title}>XenoSys</Text>
          <Text style={styles.subtitle}>Mobile Remote</Text>
          
          <Text style={styles.description}>
            Connect to your XenoSys Desktop to control agents, approve requests, and monitor system status from anywhere.
          </Text>

          <TouchableOpacity style={styles.primaryButton} onPress={() => setMode('scan')}>
            <Text style={styles.primaryButtonText}>Scan QR Code</Text>
          </TouchableOpacity>

          <TouchableOpacity style={styles.secondaryButton} onPress={() => setMode('manual')}>
            <Text style={styles.secondaryButtonText}>Enter Manually</Text>
          </TouchableOpacity>
        </View>

        <Text style={styles.footer}>
          Generate a QR code from your Desktop app
        </Text>
      </View>
    );
  }

  // Manual Entry
  if (mode === 'manual') {
    return (
      <View style={styles.container}>
        <View style={styles.header}>
          <TouchableOpacity onPress={() => setMode('welcome')}>
            <Text style={styles.backButton}>← Back</Text>
          </TouchableOpacity>
          <Text style={styles.headerTitle}>Manual Pairing</Text>
        </View>

        <View style={styles.content}>
          <Text style={styles.inputLabel}>Tunnel URL</Text>
          <TextInput
            style={styles.input}
            value={manualUrl}
            onChangeText={setManualUrl}
            placeholder="https://your-tunnel.trycloudflare.com"
            placeholderTextColor="#666"
            autoCapitalize="none"
            autoCorrect={false}
          />

          <Text style={styles.inputLabel}>Token</Text>
          <TextInput
            style={styles.input}
            value={manualToken}
            onChangeText={setManualToken}
            placeholder="Your Cloudflare Zero Trust Token"
            placeholderTextColor="#666"
            secureTextEntry
          />

          <TouchableOpacity 
            style={[styles.primaryButton, isLoading && styles.buttonDisabled]} 
            onPress={handleManualPair}
            disabled={isLoading}
          >
            <Text style={styles.primaryButtonText}>
              {isLoading ? 'Connecting...' : 'Connect'}
            </Text>
          </TouchableOpacity>

          {error && <Text style={styles.errorText}>{error}</Text>}
        </View>
      </View>
    );
  }

  // Camera Scan
  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={() => setMode('welcome')}>
          <Text style={styles.backButton}>← Back</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Scan QR Code</Text>
      </View>

      <View style={styles.content}>
        {!permission?.granted ? (
          <View style={styles.permissionContainer}>
            <Text style={styles.permissionText}>
              Camera permission required
            </Text>
            <TouchableOpacity style={styles.primaryButton} onPress={requestPermission}>
              <Text style={styles.primaryButtonText}>Grant Permission</Text>
            </TouchableOpacity>
          </View>
        ) : (
          <View style={styles.cameraContainer}>
            <Text style={styles.cameraPlaceholder}>
              📷 Camera preview would appear here
            </Text>
            <Text style={styles.cameraHint}>
              Point camera at Desktop QR code
            </Text>
          </View>
        )}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0A0A0A',
  },
  header: {
    height: 60,
    paddingHorizontal: 16,
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  backButton: {
    color: '#00B8FF',
    fontSize: 16,
  },
  headerTitle: {
    color: '#00FF9D',
    fontSize: 18,
    fontWeight: 'bold',
    marginLeft: 16,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 32,
  },
  logo: {
    fontSize: 64,
    marginBottom: 16,
  },
  title: {
    color: '#00FF9D',
    fontSize: 32,
    fontWeight: 'bold',
  },
  subtitle: {
    color: '#666',
    fontSize: 16,
    marginBottom: 24,
  },
  description: {
    color: '#888',
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 32,
  },
  primaryButton: {
    backgroundColor: '#00FF9D',
    paddingVertical: 16,
    paddingHorizontal: 32,
    borderRadius: 12,
    width: '100%',
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonText: {
    color: '#0A0A0A',
    fontSize: 16,
    fontWeight: 'bold',
  },
  secondaryButton: {
    paddingVertical: 16,
    width: '100%',
    alignItems: 'center',
  },
  secondaryButtonText: {
    color: '#00B8FF',
    fontSize: 16,
  },
  buttonDisabled: {
    opacity: 0.5,
  },
  footer: {
    color: '#444',
    fontSize: 12,
    textAlign: 'center',
    paddingBottom: 32,
  },
  inputLabel: {
    color: '#666',
    fontSize: 14,
    alignSelf: 'flex-start',
    marginBottom: 8,
  },
  input: {
    width: '100%',
    backgroundColor: '#121212',
    borderRadius: 12,
    padding: 16,
    color: '#E0E0E0',
    fontSize: 15,
    marginBottom: 20,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  errorText: {
    color: '#FF3366',
    fontSize: 14,
    marginTop: 12,
  },
  permissionContainer: {
    alignItems: 'center',
  },
  permissionText: {
    color: '#666',
    fontSize: 14,
    marginBottom: 16,
  },
  cameraContainer: {
    width: 250,
    height: 250,
    backgroundColor: '#121212',
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 2,
    borderColor: '#2A2A2A',
    borderStyle: 'dashed',
  },
  cameraPlaceholder: {
    color: '#444',
    fontSize: 14,
  },
  cameraHint: {
    color: '#666',
    fontSize: 12,
    marginTop: 12,
  },
});

export default PairingScreen;