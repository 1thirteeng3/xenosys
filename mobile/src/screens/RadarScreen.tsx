/**
 * Radar Screen - Mobile HITL Queue
 * Swipe-to-approve for intentional friction
 * Prevents accidental pocket approvals
 */

import React, { useState } from 'react';
import { View, Text, ScrollView, TouchableOpacity, StyleSheet, Alert } from 'react-native';
import { GestureDetector, Gesture } from 'react-native-gesture-handler';
import { useSpring, useAnimatedStyle, withSpring } from 'react-native-reanimated';
import { X, Check, AlertTriangle, DollarSign } from 'react-native-svg'; // Using emoji as fallback

interface HITLRequest {
  id: string;
  type: 'financial' | 'operational' | 'security';
  description: string;
  amount?: number;
  risk: 'low' | 'medium' | 'high';
  agent: string;
  timestamp: Date;
}

const MOCK_REQUESTS: HITLRequest[] = [
  {
    id: '1',
    type: 'financial',
    description: 'Payment to AWS infrastructure',
    amount: 1250.00,
    risk: 'high',
    agent: 'FinanceBot',
    timestamp: new Date(),
  },
  {
    id: '2',
    type: 'operational',
    description: 'Deploy staging environment',
    risk: 'medium',
    agent: 'DeployBot',
    timestamp: new Date(Date.now() - 60000),
  },
  {
    id: '3',
    type: 'security',
    description: 'Revoke session token',
    risk: 'low',
    agent: 'SecurityBot',
    timestamp: new Date(Date.now() - 120000),
  },
];

// Animated Approval Card
const ApprovalCard: React.FC<{
  request: HITLRequest;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}> = ({ request, onApprove, onReject }) => {
  const translateX = useSpring(0);

  // Swipe gesture
  const gesture = Gesture.Pan()
    .onUpdate((event) => {
      translateX.value = event.translationX;
    })
    .onEnd((event) => {
      if (event.translationX > 150) {
        // Swiped right - approve
        onApprove(request.id);
        translateX.value = withSpring(500);
      } else if (event.translationX < -150) {
        // Swiped left - reject
        onReject(request.id);
        translateX.value = withSpring(-500);
      } else {
        // Return to center
        translateX.value = withSpring(0);
      }
    });

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
  }));

  const getTypeColor = () => {
    switch (request.type) {
      case 'financial': return '#FFB000';
      case 'security': return '#FF3366';
      default: return '#00B8FF';
    }
  };

  return (
    <View style={styles.cardWrapper}>
      {/* Background indicators */}
      <View style={[styles.swipeBackground, styles.approveBackground]}>
        <Text style={styles.swipeIcon}>✓</Text>
      </View>
      <View style={[styles.swipeBackground, styles.rejectBackground]}>
        <Text style={styles.swipeIcon}>✗</Text>
      </View>

      {/* Card */}
      <GestureDetector gesture={gesture}>
        <Animated.View style={[styles.card, animatedStyle]}>
          <View style={styles.cardHeader}>
            <View style={[styles.typeBadge, { backgroundColor: getTypeColor() + '20' }]}>
              <Text style={[styles.typeText, { color: getTypeColor() }]}>
                {request.type.toUpperCase()}
              </Text>
            </View>
            <Text style={styles.agentText}>{request.agent}</Text>
          </View>

          <Text style={styles.descriptionText}>{request.description}</Text>

          {request.amount && (
            <View style={styles.amountRow}>
              <Text style={styles.amountLabel}>$</Text>
              <Text style={styles.amountText}>{request.amount.toLocaleString()}</Text>
            </View>
          )}

          <View style={styles.riskRow}>
            <Text style={[
              styles.riskText,
              request.risk === 'high' && styles.riskHigh,
              request.risk === 'medium' && styles.riskMedium,
              request.risk === 'low' && styles.riskLow,
            ]}>
              {request.risk.toUpperCase()} RISK
            </Text>
          </View>

          <Text style={styles.swipeHint}>← Swipe to respond →</Text>
        </Animated.View>
      </GestureDetector>
    </View>
  );
};

export const RadarScreen = () => {
  const [requests, setRequests] = useState<HITLRequest[]>(MOCK_REQUESTS);

  const handleApprove = (id: string) => {
    Alert.alert('Approved', 'Request has been approved', [
      { text: 'OK', onPress: () => setRequests(prev => prev.filter(r => r.id !== id)) }
    ]);
  };

  const handleReject = (id: string) => {
    Alert.alert('Rejected', 'Request has been rejected', [
      { text: 'OK', onPress: () => setRequests(prev => prev.filter(r => r.id !== id)) }
    ]);
  };

  return (
    <View style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Radar</Text>
        {requests.length > 0 && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{requests.length}</Text>
          </View>
        )}
      </View>

      {/* Request List */}
      <ScrollView style={styles.list} contentContainerStyle={styles.listContent}>
        {requests.length === 0 ? (
          <View style={styles.emptyState}>
            <Text style={styles.emptyIcon}>📭</Text>
            <Text style={styles.emptyText}>All clear!</Text>
            <Text style={styles.emptySubtext}>No pending approvals</Text>
          </View>
        ) : (
          requests.map(request => (
            <ApprovalCard
              key={request.id}
              request={request}
              onApprove={handleApprove}
              onReject={handleReject}
            />
          ))
        )}
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
  badge: {
    backgroundColor: '#FF3366',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  badgeText: {
    color: '#fff',
    fontWeight: 'bold',
    fontSize: 14,
  },
  list: {
    flex: 1,
  },
  listContent: {
    padding: 16,
    gap: 16,
  },
  cardWrapper: {
    position: 'relative',
    height: 180,
  },
  swipeBackground: {
    position: 'absolute',
    top: 0,
    bottom: 0,
    width: '100%',
    borderRadius: 16,
    justifyContent: 'center',
    alignItems: 'center',
  },
  approveBackground: {
    backgroundColor: '#00FF9D30',
    right: 0,
  },
  rejectBackground: {
    backgroundColor: '#FF336630',
    left: 0,
  },
  swipeIcon: {
    fontSize: 32,
    fontWeight: 'bold',
  },
  card: {
    backgroundColor: '#121212',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: '#2A2A2A',
    height: '100%',
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  typeBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
  },
  typeText: {
    fontSize: 12,
    fontWeight: 'bold',
  },
  agentText: {
    color: '#666',
    fontSize: 12,
  },
  descriptionText: {
    color: '#E0E0E0',
    fontSize: 15,
    marginBottom: 12,
  },
  amountRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  amountLabel: {
    color: '#FFB000',
    fontSize: 16,
    fontWeight: 'bold',
  },
  amountText: {
    color: '#FFB000',
    fontSize: 20,
    fontWeight: 'bold',
  },
  riskRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  riskText: {
    fontSize: 11,
    fontWeight: 'bold',
  },
  riskHigh: {
    color: '#FF3366',
  },
  riskMedium: {
    color: '#FFB000',
  },
  riskLow: {
    color: '#00FF9D',
  },
  swipeHint: {
    position: 'absolute',
    bottom: 12,
    right: 16,
    color: '#444',
    fontSize: 11,
  },
  emptyState: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingTop: 100,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  emptyText: {
    color: '#00FF9D',
    fontSize: 20,
    fontWeight: 'bold',
  },
  emptySubtext: {
    color: '#666',
    fontSize: 14,
    marginTop: 8,
  },
});

export default RadarScreen;