/**
 * Status Screen - Connection Diagnostics
 * Shows system health and connection details
 */

import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, Linking, Alert } from 'react-native';
import { useTunnelHealth } from '../hooks/useTunnelHealth';

interface SystemMetric {
  label: string;
  value: string;
  isGood: boolean;
}

export const StatusScreen = () => {
  const { isConnected, isPaired, latency, error, unpair } = useTunnelHealth();
  
  const [metrics, setMetrics] = useState<SystemMetric[]>([
    { label: 'API', value: 'Online', isGood: true },
    { label: 'Cache', value: 'Active', isGood: true },
    { label: 'Tunnel', value: 'Stable', isGood: true },
  ]);

  const handleUnpair = () => {
    Alert.alert(
      'Unpair Device',
      'This will disconnect from the XenoSys desktop. You will need to re-scan the QR code to connect again.',
      [
        { text: 'Cancel', style: 'cancel' },
        { 
          text: 'Unpair', 
          style: 'destructive',
          onPress: async () => {
            await unpair();
          }
        },
      ]
    );
  };

  const openSettings = () => {
    // Would open native settings
    Alert.alert('Settings', 'Native settings integration coming soon');
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Status</Text>
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.contentContainer}>
        {/* Connection Status */}
        <View style={styles.section}>
          <View style={styles.statusCard}>
            <View style={[
              styles.statusIndicator,
              isConnected ? styles.statusConnected : styles.statusDisconnected
            ]} />
            <Text style={styles.statusTitle}>
              {isConnected ? 'Connected' : 'Offline'}
            </Text>
            {latency > 0 && (
              <Text style={styles.statusLatency}>{latency}ms</Text>
            )}
          </View>
          {error && (
            <Text style={styles.errorText}>{error}</Text>
          )}
        </View>

        {/* System Metrics */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>SYSTEM</Text>
          <View style={styles.metricsCard}>
            {metrics.map((metric, index) => (
              <View key={index} style={styles.metricRow}>
                <Text style={styles.metricLabel}>{metric.label}</Text>
                <View style={styles.metricValue}>
                  <View style={[
                    styles.metricDot,
                    { backgroundColor: metric.isGood ? '#00FF9D' : '#FF3366' }
                  ]} />
                  <Text style={styles.metricText}>{metric.value}</Text>
                </View>
              </View>
            ))}
          </View>
        </View>

        {/* Device Info */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>DEVICE</Text>
          <View style={styles.infoCard}>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Paired</Text>
              <Text style={styles.infoValue}>{isPaired ? 'Yes' : 'No'}</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>App Version</Text>
              <Text style={styles.infoValue}>1.0.0</Text>
            </View>
            <View style={styles.infoRow}>
              <Text style={styles.infoLabel}>Platform</Text>
              <Text style={styles.infoValue}>React Native</Text>
            </View>
          </View>
        </View>

        {/* About */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>ABOUT</Text>
          <View style={styles.aboutCard}>
            <Text style={styles.aboutTitle}>XenoSys</Text>
            <Text style={styles.aboutSubtitle}>Cognitive Engine</Text>
            <Text style={styles.aboutText}>
              Control • Transparency • Sovereignty
            </Text>
          </View>
        </View>

        {/* Actions */}
        <View style={styles.section}>
          <TouchableOpacity style={styles.actionButton} onPress={openSettings}>
            <Text style={styles.actionButtonText}>Open Settings</Text>
          </TouchableOpacity>
          
          <TouchableOpacity 
            style={styles.unpairButton} 
            onPress={handleUnpair}
          >
            <Text style={styles.unpairButtonText}>Unpair Device</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
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
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  headerTitle: {
    color: '#00FF9D',
    fontSize: 18,
    fontWeight: 'bold',
  },
  content: {
    flex: 1,
  },
  contentContainer: {
    padding: 16,
  },
  section: {
    marginBottom: 24,
  },
  statusCard: {
    backgroundColor: '#121212',
    borderRadius: 16,
    padding: 20,
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  statusIndicator: {
    width: 12,
    height: 12,
    borderRadius: 6,
    marginRight: 12,
  },
  statusConnected: {
    backgroundColor: '#00FF9D',
  },
  statusDisconnected: {
    backgroundColor: '#FF3366',
  },
  statusTitle: {
    color: '#E0E0E0',
    fontSize: 18,
    fontWeight: '600',
    flex: 1,
  },
  statusLatency: {
    color: '#666',
    fontSize: 14,
  },
  errorText: {
    color: '#FF3366',
    fontSize: 12,
    marginTop: 8,
  },
  sectionTitle: {
    color: '#00B8FF',
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 12,
  },
  metricsCard: {
    backgroundColor: '#121212',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  metricRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  metricLabel: {
    color: '#666',
    fontSize: 14,
  },
  metricValue: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  metricDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  metricText: {
    color: '#E0E0E0',
    fontSize: 14,
  },
  infoCard: {
    backgroundColor: '#121212',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 8,
  },
  infoLabel: {
    color: '#666',
    fontSize: 14,
  },
  infoValue: {
    color: '#E0E0E0',
    fontSize: 14,
  },
  aboutCard: {
    backgroundColor: '#121212',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  aboutTitle: {
    color: '#00FF9D',
    fontSize: 24,
    fontWeight: 'bold',
  },
  aboutSubtitle: {
    color: '#666',
    fontSize: 14,
    marginTop: 4,
  },
  aboutText: {
    color: '#00B8FF',
    fontSize: 12,
    marginTop: 16,
  },
  actionButton: {
    backgroundColor: '#121212',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2A2A2A',
    marginBottom: 12,
  },
  actionButtonText: {
    color: '#E0E0E0',
    fontSize: 16,
  },
  unpairButton: {
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
  },
  unpairButtonText: {
    color: '#FF3366',
    fontSize: 16,
  },
});

export default StatusScreen;