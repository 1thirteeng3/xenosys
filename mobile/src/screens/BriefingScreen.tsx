/**
 * Briefing Screen - Daily Summary
 * Quick overview of system status
 */

import React from 'react';
import { View, Text, ScrollView, StyleSheet } from 'react-native';
import { useTunnelHealth } from '../hooks/useTunnelHealth';

interface BriefItem {
  id: string;
  title: string;
  value: string;
  status: 'good' | 'warning' | 'error';
}

const MOCK_BRIEF: BriefItem[] = [
  { id: '1', title: 'Active Agents', value: '3', status: 'good' },
  { id: '2', title: 'Memory Usage', value: '2.4 GB', status: 'good' },
  { id: '3', title: 'Pending HITL', value: '2', status: 'warning' },
  { id: '4', title: 'Model Status', value: 'Ready', status: 'good' },
  { id: '5', title: 'API Latency', value: '142ms', status: 'good' },
];

export const BriefingScreen = () => {
  const { isConnected, latency, pendingCount } = useTunnelHealth();

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'good': return '#00FF9D';
      case 'warning': return '#FFB000';
      case 'error': return '#FF3366';
      default: return '#666';
    }
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Briefing</Text>
        <Text style={styles.headerDate}>
          {new Date().toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })}
        </Text>
      </View>

      <ScrollView style={styles.content} contentContainerStyle={styles.contentContainer}>
        {/* Quick Stats Grid */}
        <View style={styles.grid}>
          {MOCK_BRIEF.map((item, index) => (
            <View key={item.id} style={styles.gridItem}>
              <Text style={styles.gridValue} value={item.value} status={item.status}>
                {item.value}
              </Text>
              <Text style={styles.gridTitle}>{item.title}</Text>
              <View style={[styles.statusDot, { backgroundColor: getStatusColor(item.status) }]} />
            </View>
          ))}
        </View>

        {/* Connection Status */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Connection</Text>
          <View style={styles.statusCard}>
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>Tunnel</Text>
              <View style={[
                styles.statusBadge,
                { backgroundColor: isConnected ? '#00FF9D20' : '#FF336620' }
              ]}>
                <Text style={[
                  styles.statusText,
                  { color: isConnected ? '#00FF9D' : '#FF3366' }
                ]}>
                  {isConnected ? 'Connected' : 'Offline'}
                </Text>
              </View>
            </View>
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>Latency</Text>
              <Text style={styles.statusValue}>{latency}ms</Text>
            </View>
            <View style={styles.statusRow}>
              <Text style={styles.statusLabel}>Pending</Text>
              <Text style={[styles.statusValue, pendingCount > 0 && styles.warningText]}>
                {pendingCount}
              </Text>
            </View>
          </View>
        </View>

        {/* Quick Actions */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Quick Actions</Text>
          <View style={styles.actionsGrid}>
            <View style={styles.actionButton}>
              <Text style={styles.actionIcon}>⚡</Text>
              <Text style={styles.actionText}>Query</Text>
            </View>
            <View style={styles.actionButton}>
              <Text style={styles.actionIcon}>📋</Text>
              <Text style={styles.actionText}>Review</Text>
            </View>
            <View style={styles.actionButton}>
              <Text style={styles.actionIcon}>🔍</Text>
              <Text style={styles.actionText}>Search</Text>
            </View>
            <View style={styles.actionButton}>
              <Text style={styles.actionIcon}>📊</Text>
              <Text style={styles.actionText}>Stats</Text>
            </View>
          </View>
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
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: '#2A2A2A',
  },
  headerTitle: {
    color: '#00FF9D',
    fontSize: 18,
    fontWeight: 'bold',
  },
  headerDate: {
    color: '#666',
    fontSize: 14,
  },
  content: {
    flex: 1,
  },
  contentContainer: {
    padding: 16,
  },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    marginBottom: 24,
  },
  gridItem: {
    width: '47%',
    backgroundColor: '#121212',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#2A2A2A',
    position: 'relative',
  },
  gridValue: {
    color: '#E0E0E0',
    fontSize: 28,
    fontWeight: 'bold',
  },
  gridTitle: {
    color: '#666',
    fontSize: 12,
    marginTop: 4,
  },
  statusDot: {
    position: 'absolute',
    top: 12,
    right: 12,
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  section: {
    marginBottom: 24,
  },
  sectionTitle: {
    color: '#00B8FF',
    fontSize: 14,
    fontWeight: '600',
    marginBottom: 12,
  },
  statusCard: {
    backgroundColor: '#121212',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
  },
  statusLabel: {
    color: '#666',
    fontSize: 14,
  },
  statusBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusText: {
    fontSize: 12,
    fontWeight: '600',
  },
  statusValue: {
    color: '#E0E0E0',
    fontSize: 14,
  },
  warningText: {
    color: '#FFB000',
  },
  actionsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  actionButton: {
    width: '47%',
    backgroundColor: '#121212',
    borderRadius: 12,
    padding: 20,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  actionIcon: {
    fontSize: 24,
    marginBottom: 8,
  },
  actionText: {
    color: '#E0E0E0',
    fontSize: 14,
  },
});

export default BriefingScreen;