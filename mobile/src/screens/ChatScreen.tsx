/**
 * Chat Screen - Mobile Conversation
 * Simple, fast text interface optimized for mobile
 */

import React, { useState } from 'react';
import { View, Text, TextInput, ScrollView, TouchableOpacity, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { useTunnelHealth } from '../hooks/useTunnelHealth';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const MOCK_MESSAGES: Message[] = [
  { id: '1', role: 'assistant', content: 'XenoSys Mobile connected. How can I assist you?', timestamp: new Date() },
];

export const ChatScreen = () => {
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>(MOCK_MESSAGES);
  const [isProcessing, setIsProcessing] = useState(false);
  const { isConnected, tunnelUrl } = useTunnelHealth();

  const handleSend = async () => {
    if (!input.trim() || isProcessing || !isConnected) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsProcessing(true);

    // Simulate API call
    setTimeout(async () => {
      try {
        const response = await fetch(`${tunnelUrl}/api/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: input }),
        });
        
        const data = await response.json();
        
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: data.response || 'Processing complete.',
          timestamp: new Date(),
        }]);
      } catch (e) {
        setMessages(prev => [...prev, {
          id: Date.now().toString(),
          role: 'assistant',
          content: 'Connection error. Please check your network.',
          timestamp: new Date(),
        }]);
      }
      setIsProcessing(false);
    }, 1500);
  };

  return (
    <KeyboardAvoidingView 
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.headerTitle}>XenoSys</Text>
        <View style={[styles.statusDot, isConnected ? styles.connected : styles.disconnected]} />
      </View>

      {/* Messages */}
      <ScrollView style={styles.messages} contentContainerStyle={styles.messagesContent}>
        {messages.map(msg => (
          <View key={msg.id} style={[styles.messageBubble, msg.role === 'user' ? styles.userBubble : styles.assistantBubble]}>
            <Text style={[styles.messageText, msg.role === 'user' ? styles.userText : styles.assistantText]}>
              {msg.content}
            </Text>
          </View>
        ))}
        {isProcessing && (
          <View style={styles.messageBubble assistantBubble}>
            <Text style={styles.typingText}>Typing...</Text>
          </View>
        )}
      </ScrollView>

      {/* Input */}
      <View style={styles.inputContainer}>
        <TextInput
          style={styles.input}
          value={input}
          onChangeText={setInput}
          placeholder={isConnected ? 'Message XenoSys...' : 'Offline - Connect first'}
          placeholderTextColor="#666"
          editable={isConnected}
          multiline
        />
        <TouchableOpacity 
          style={[styles.sendButton, (!input.trim() || !isConnected) && styles.sendButtonDisabled]}
          onPress={handleSend}
          disabled={!input.trim() || !isConnected}
        >
          <Text style={styles.sendButtonText}>→</Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
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
  statusDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  connected: {
    backgroundColor: '#00FF9D',
  },
  disconnected: {
    backgroundColor: '#FF3366',
  },
  messages: {
    flex: 1,
  },
  messagesContent: {
    padding: 16,
    gap: 12,
  },
  messageBubble: {
    maxWidth: '80%',
    padding: 12,
    borderRadius: 16,
  },
  userBubble: {
    alignSelf: 'flex-end',
    backgroundColor: '#00FF9D20',
    borderWidth: 1,
    borderColor: '#00FF9D30',
  },
  assistantBubble: {
    alignSelf: 'flex-start',
    backgroundColor: '#121212',
    borderWidth: 1,
    borderColor: '#2A2A2A',
  },
  messageText: {
    fontSize: 15,
    lineHeight: 20,
  },
  userText: {
    color: '#00FF9D',
  },
  assistantText: {
    color: '#E0E0E0',
  },
  typingText: {
    color: '#00B8FF',
    fontStyle: 'italic',
  },
  inputContainer: {
    flexDirection: 'row',
    padding: 12,
    gap: 8,
    borderTopWidth: 1,
    borderTopColor: '#2A2A2A',
  },
  input: {
    flex: 1,
    backgroundColor: '#121212',
    borderRadius: 20,
    paddingHorizontal: 16,
    paddingVertical: 10,
    color: '#E0E0E0',
    fontSize: 15,
    maxHeight: 100,
  },
  sendButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: '#00FF9D',
    justifyContent: 'center',
    alignItems: 'center',
  },
  sendButtonDisabled: {
    backgroundColor: '#333',
  },
  sendButtonText: {
    color: '#0A0A0A',
    fontSize: 20,
    fontWeight: 'bold',
  },
});

export default ChatScreen;