import React, { useState } from 'react';
import {
  View, Text, TouchableOpacity, TextInput,
  StyleSheet, Alert, ScrollView, ActivityIndicator,
} from 'react-native';
import { Feather } from '@expo/vector-icons';

import { colors, sharedStyles } from '../../styles/theme';
import { BACKEND_URL } from '../../firebaseConfig';

export default function ProfileTab({ session, shop, products, orders, onLogout, onRefreshShop }) {
  const [editingShop, setEditingShop] = useState(false);
  const [shopName, setShopName] = useState(shop?.name || '');
  const [shopAddress, setShopAddress] = useState(shop?.address || '');
  const [loading, setLoading] = useState(false);

  const totalRevenue = orders
    .filter(o => o.payment_status === 'paid')
    .reduce((sum, o) => sum + (o.total_amount || 0), 0);
  const totalOrders = orders.length;
  const approvedOrders = orders.filter(o => o.status === 'approved').length;

  const handleUpdateShop = async () => {
    if (!shopName.trim()) { Alert.alert('Error', 'Shop name cannot be empty.'); return; }
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/shops/${shop.id}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ name: shopName.trim(), address: shopAddress.trim() || null }),
      });
      if (res.ok) {
        Alert.alert('Success', 'Shop details updated.');
        setEditingShop(false);
        onRefreshShop();
      } else {
        Alert.alert('Error', 'Failed to update shop.');
      }
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    Alert.alert('Logout', 'Are you sure you want to logout?', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Logout', style: 'destructive', onPress: onLogout },
    ]);
  };

  return (
    <View style={sharedStyles.screen}>
      <View style={sharedStyles.header}>
        <Text style={sharedStyles.headerTitle}>👤 Profile</Text>
        <TouchableOpacity onPress={handleLogout} style={styles.logoutBtn}>
          <Feather name="log-out" size={18} color="rgba(255,255,255,0.9)" />
          <Text style={{ color: 'rgba(255,255,255,0.9)', fontWeight: '600', fontSize: 13, marginLeft: 4 }}>Logout</Text>
        </TouchableOpacity>
      </View>

      <ScrollView contentContainerStyle={{ padding: 16 }}>
        {/* Owner info */}
        <View style={[sharedStyles.card, styles.ownerCard]}>
          <View style={styles.avatarCircle}>
            <Text style={styles.avatarText}>
              {(session.owner_name || session.phone_number || 'O')[0].toUpperCase()}
            </Text>
          </View>
          <Text style={styles.ownerName}>{session.owner_name || 'Shop Owner'}</Text>
          <Text style={sharedStyles.smallText}>{session.phone_number}</Text>
          <View style={[sharedStyles.badge, { backgroundColor: colors.primaryLight, marginTop: 8 }]}>
            <Text style={[sharedStyles.badgeText, { color: colors.primary }]}>🏪 Shop Owner</Text>
          </View>
        </View>

        {/* Stats */}
        <View style={{ flexDirection: 'row', gap: 12, marginBottom: 12 }}>
          <View style={[sharedStyles.card, { flex: 1, alignItems: 'center' }]}>
            <Feather name="shopping-cart" size={24} color={colors.primary} style={{ marginBottom: 6 }} />
            <Text style={{ fontSize: 22, fontWeight: '900', color: colors.primary }}>{totalOrders}</Text>
            <Text style={sharedStyles.smallText}>Total Orders</Text>
          </View>
          <View style={[sharedStyles.card, { flex: 1, alignItems: 'center' }]}>
            <Feather name="package" size={24} color={colors.secondary} style={{ marginBottom: 6 }} />
            <Text style={{ fontSize: 22, fontWeight: '900', color: colors.secondary }}>{products.length}</Text>
            <Text style={sharedStyles.smallText}>Products</Text>
          </View>
          <View style={[sharedStyles.card, { flex: 1, alignItems: 'center' }]}>
            <Feather name="trending-up" size={24} color={colors.warning} style={{ marginBottom: 6 }} />
            <Text style={{ fontSize: 18, fontWeight: '900', color: colors.warning }}>
              ₹{totalRevenue.toFixed(0)}
            </Text>
            <Text style={sharedStyles.smallText}>Revenue</Text>
          </View>
        </View>

        {/* Shop details */}
        <View style={sharedStyles.card}>
          <View style={sharedStyles.sectionHeader}>
            <Text style={sharedStyles.sectionTitle}>🏪 Shop Details</Text>
            <TouchableOpacity onPress={() => setEditingShop(!editingShop)}>
              <Feather name={editingShop ? 'x' : 'edit-2'} size={18} color={colors.primary} />
            </TouchableOpacity>
          </View>

          {editingShop ? (
            <>
              <Text style={sharedStyles.label}>Shop Name *</Text>
              <TextInput
                style={sharedStyles.input}
                value={shopName}
                onChangeText={setShopName}
                placeholder="Shop Name"
              />
              <Text style={sharedStyles.label}>Shop Address</Text>
              <TextInput
                style={[sharedStyles.input, { height: 80, textAlignVertical: 'top' }]}
                value={shopAddress}
                onChangeText={setShopAddress}
                placeholder="Enter address..."
                multiline
              />
              <TouchableOpacity
                style={[sharedStyles.btnPrimary, loading && sharedStyles.btnDisabled]}
                onPress={handleUpdateShop}
                disabled={loading}
              >
                {loading ? <ActivityIndicator color="#fff" /> : <Text style={sharedStyles.btnPrimaryText}>Save Changes</Text>}
              </TouchableOpacity>
            </>
          ) : (
            <>
              <InfoRow icon="store" label="Shop Name" value={shop?.name || '—'} />
              <InfoRow icon="map-pin" label="Address" value={shop?.address || 'Not set'} />
              <InfoRow icon="hash" label="Shop ID" value={`#${shop?.id}`} />
            </>
          )}
        </View>

        {/* Account info */}
        <View style={sharedStyles.card}>
          <Text style={[sharedStyles.sectionTitle, { marginBottom: 12 }]}>Account Info</Text>
          <InfoRow icon="phone" label="Phone" value={session.phone_number} />
          <InfoRow icon="shield" label="Role" value="Shop Owner" />
          <InfoRow icon="check-circle" label="Status" value="Active" valueColor={colors.secondary} />
        </View>

        {/* App version */}
        <Text style={[sharedStyles.smallText, { textAlign: 'center', marginTop: 8, marginBottom: 24 }]}>
          RetailAutomate Mobile v1.0.0
        </Text>
      </ScrollView>
    </View>
  );
}

function InfoRow({ icon, label, value, valueColor }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.surfaceBorder }}>
      <Feather name={icon} size={16} color={colors.textSecondary} style={{ marginRight: 12 }} />
      <Text style={[sharedStyles.smallText, { flex: 1 }]}>{label}</Text>
      <Text style={{ fontSize: 14, fontWeight: '600', color: valueColor || colors.textPrimary }}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  logoutBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  ownerCard: {
    alignItems: 'center',
    paddingVertical: 24,
  },
  avatarCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.primary,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 12,
  },
  avatarText: {
    fontSize: 28,
    fontWeight: '900',
    color: '#fff',
  },
  ownerName: {
    fontSize: 20,
    fontWeight: '800',
    color: colors.textPrimary,
  },
});
