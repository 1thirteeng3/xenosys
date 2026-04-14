/**
 * XenoSys Mobile - Navigation Configuration
 * Bottom Tab Navigator with 4 tabs:
 * - Chat, Radar, Briefing, Status
 */

import React from 'react';
import { NavigationContainer } from '@react-navigation/native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { View, Text, StyleSheet } from 'react-native';

import { ChatScreen } from '../screens/ChatScreen';
import { RadarScreen } from '../screens/RadarScreen';
import { BriefingScreen } from '../screens/BriefingScreen';
import { StatusScreen } from '../screens/StatusScreen';
import { PairingScreen } from '../screens/PairingScreen';
import { useTunnelHealth } from '../hooks/useTunnelHealth';

// Tab icon component using text emoji fallback
const TabIcon = ({ 
  name, 
  focused, 
  badge = 0 
}: { 
  name: string; 
  focused: boolean;
  badge?: number;
}) => {
  const icons: Record<string, string> = {
    chat: '💬',
    radar: '📡',
    briefing: '📄',
    status: '⚡',
  };

  return (
    <View style={styles.iconContainer}>
      <Text style={[styles.icon, focused && styles.iconFocused]}>
        {icons[name]}
      </Text>
      {badge > 0 && (
        <View style={styles.badge}>
          <Text style={styles.badgeText}>{badge > 9 ? '9+' : badge}</Text>
        </View>
      )}
    </View>
  );
};

const Tab = createBottomTabNavigator();
const Stack = createNativeStackNavigator();

// Main Tab Navigator
const MainTabs = () => {
  const { pendingCount } = useTunnelHealth();

  return (
    <Tab.Navigator
      screenOptions={{
        headerShown: false,
        tabBarStyle: styles.tabBar,
        tabBarActiveTintColor: '#00FF9D',
        tabBarInactiveTintColor: '#666',
        tabBarLabelStyle: styles.tabLabel,
      }}
    >
      <Tab.Screen
        name="Chat"
        component={ChatScreen}
        options={{
          tabBarIcon: ({ focused }) => <TabIcon name="chat" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Radar"
        component={RadarScreen}
        options={{
          tabBarIcon: ({ focused }) => (
            <TabIcon name="radar" focused={focused} badge={pendingCount} />
          ),
        }}
      />
      <Tab.Screen
        name="Briefing"
        component={BriefingScreen}
        options={{
          tabBarIcon: ({ focused }) => <TabIcon name="briefing" focused={focused} />,
        }}
      />
      <Tab.Screen
        name="Status"
        component={StatusScreen}
        options={{
          tabBarIcon: ({ focused }) => <TabIcon name="status" focused={focused} />,
        }}
      />
    </Tab.Navigator>
  );
};

// Root Navigator (includes pairing flow)
export const AppNavigator = () => {
  const { isPaired, isLoading } = useTunnelHealth();

  if (isLoading) {
    return (
      <View style={styles.loadingContainer}>
        <Text style={styles.loadingText}>Connecting...</Text>
      </View>
    );
  }

  if (!isPaired) {
    return <PairingScreen />;
  }

  return (
    <NavigationContainer>
      <MainTabs />
    </NavigationContainer>
  );
};

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: '#121212',
    borderTopColor: '#2A2A2A',
    borderTopWidth: 1,
    height: 85,
    paddingBottom: 25,
    paddingTop: 8,
  },
  tabLabel: {
    fontSize: 11,
    fontWeight: '500',
  },
  iconContainer: {
    position: 'relative',
  },
  icon: {
    fontSize: 22,
    opacity: 0.6,
  },
  iconFocused: {
    opacity: 1,
  },
  badge: {
    position: 'absolute',
    top: -6,
    right: -10,
    backgroundColor: '#FF3366',
    borderRadius: 10,
    minWidth: 18,
    height: 18,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: 4,
  },
  badgeText: {
    color: '#fff',
    fontSize: 10,
    fontWeight: 'bold',
  },
  loadingContainer: {
    flex: 1,
    backgroundColor: '#0A0A0A',
    justifyContent: 'center',
    alignItems: 'center',
  },
  loadingText: {
    color: '#00B8FF',
    fontSize: 16,
    fontWeight: '500',
    marginTop: 16,
  },
});

export default AppNavigator;