import React, { useState } from 'react';
import {
  View, Text, FlatList, TouchableOpacity,
  StyleSheet, ScrollView,
} from 'react-native';
import { Feather } from '@expo/vector-icons';

import { colors, sharedStyles } from '../../styles/theme';
import { BACKEND_URL } from '../../firebaseConfig';
import { formatDateTime } from '../../utils/dateTimeUtils';

export default function AlertsTab({ session, shop, alerts, onRefreshAlerts }) {
  const [filter, setFilter] = useState('all'); // 'all' | 'unread' | 'low_stock' | 'order'

  const filteredAlerts = alerts.filter(a => {
    if (filter === 'all') return true;
    if (filter === 'unread') return !a.is_read;
    if (filter === 'low_stock') return a.type === 'low_stock';
    if (filter === 'order') return a.type === 'new_order' || a.type === 'order_update';
    return true;
  });

  const markRead = async (alertId) => {
    try {
      await fetch(`${BACKEND_URL}/api/alerts/${alertId}/read`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${session.access_token}` },
      });
      onRefreshAlerts();
    } catch (e) {}
  };

  const markAllRead = async () => {
    if (!shop) return;
    try {
      await fetch(`${BACKEND_URL}/api/alerts/mark-all-read?shop_id=${shop.id}`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${session.access_token}` },
      });
      onRefreshAlerts();
    } catch (e) {}
  };

  const getAlertIcon = (type) => {
    if (type === 'low_stock') return { name: 'alert-triangle', color: colors.warning };
    if (type === 'new_order') return { name: 'shopping-cart', color: colors.primary };
    if (type === 'payment_success') return { name: 'check-circle', color: colors.secondary };
    return { name: 'bell', color: colors.textSecondary };
  };

  const unreadCount = alerts.filter(a => !a.is_read).length;

  return (
    <View style={sharedStyles.screen}>
      <View style={sharedStyles.header}>
        <View style={{ flex: 1 }}>
          <Text style={sharedStyles.headerTitle}>🔔 Alerts</Text>
          <Text style={sharedStyles.headerSubtitle}>
            {unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'}
          </Text>
        </View>
        <View style={{ flexDirection: 'row', gap: 8 }}>
          {unreadCount > 0 && (
            <TouchableOpacity onPress={markAllRead} style={styles.headerBtn}>
              <Text style={{ color: '#fff', fontSize: 12, fontWeight: '600' }}>Mark All Read</Text>
            </TouchableOpacity>
          )}
          <TouchableOpacity onPress={onRefreshAlerts} style={{ padding: 8 }}>
            <Feather name="refresh-cw" size={18} color="rgba(255,255,255,0.8)" />
          </TouchableOpacity>
        </View>
      </View>

      {/* Filter chips */}
      <ScrollView horizontal showsHorizontalScrollIndicator={false}
        style={{ flexGrow: 0, backgroundColor: colors.surface, borderBottomWidth: 1, borderBottomColor: colors.surfaceBorder }}
        contentContainerStyle={{ paddingHorizontal: 16, paddingVertical: 10, gap: 8 }}
      >
        {[
          { key: 'all', label: `All (${alerts.length})` },
          { key: 'unread', label: `Unread (${unreadCount})` },
          { key: 'low_stock', label: 'Low Stock' },
          { key: 'order', label: 'Orders' },
        ].map(f => (
          <TouchableOpacity
            key={f.key}
            onPress={() => setFilter(f.key)}
            style={[styles.chip, filter === f.key && styles.chipActive]}
          >
            <Text style={[styles.chipText, filter === f.key && styles.chipTextActive]}>
              {f.label}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {filteredAlerts.length === 0 ? (
        <View style={sharedStyles.emptyContainer}>
          <Feather name="bell-off" size={48} color={colors.textMuted} />
          <Text style={sharedStyles.emptyText}>No alerts found.</Text>
        </View>
      ) : (
        <FlatList
          data={filteredAlerts}
          keyExtractor={item => String(item.id)}
          contentContainerStyle={{ padding: 16 }}
          renderItem={({ item: alert }) => {
            const icon = getAlertIcon(alert.type);
            return (
              <TouchableOpacity
                style={[sharedStyles.card, !alert.is_read && styles.unreadCard]}
                onPress={() => markRead(alert.id)}
                activeOpacity={0.8}
              >
                <View style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 12 }}>
                  <View style={[styles.iconCircle, { backgroundColor: icon.color + '20' }]}>
                    <Feather name={icon.name} size={20} color={icon.color} />
                  </View>
                  <View style={{ flex: 1 }}>
                    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                      <Text style={{ fontWeight: '700', fontSize: 14, color: colors.textPrimary }}>
                        {alert.title || alertTitle(alert.type)}
                      </Text>
                      {!alert.is_read && <View style={styles.unreadDot} />}
                    </View>
                    <Text style={sharedStyles.smallText}>{alert.message}</Text>
                    <Text style={[sharedStyles.smallText, { marginTop: 4, color: colors.textMuted }]}>
                      {formatDateTime(alert.created_at)}
                    </Text>
                  </View>
                </View>
              </TouchableOpacity>
            );
          }}
        />
      )}
    </View>
  );
}

const alertTitle = (type) => {
  if (type === 'low_stock') return '⚠️ Low Stock Alert';
  if (type === 'new_order') return '🛒 New Order';
  if (type === 'payment_success') return '💰 Payment Received';
  return '🔔 Notification';
};

const styles = StyleSheet.create({
  headerBtn: {
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 6,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  chip: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    backgroundColor: colors.surfaceLight,
  },
  chipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  chipText: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
  },
  chipTextActive: {
    color: '#fff',
  },
  unreadCard: {
    borderLeftWidth: 4,
    borderLeftColor: colors.primary,
    backgroundColor: colors.primaryLight,
  },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
  },
  unreadDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.primary,
  },
});
