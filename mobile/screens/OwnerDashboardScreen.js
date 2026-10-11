import React, { useState, useEffect, useRef } from 'react';
import {
  View, Text, TouchableOpacity, StyleSheet, Alert,
} from 'react-native';
import { createBottomTabNavigator } from '@react-navigation/bottom-tabs';
import { NavigationContainer } from '@react-navigation/native';
import { Feather } from '@expo/vector-icons';

import { colors, sharedStyles } from '../styles/theme';
import { BACKEND_URL, getWebSocketUrl } from '../firebaseConfig';

import OrdersTab from './tabs/OrdersTab';
import InventoryTab from './tabs/InventoryTab';
import AlertsTab from './tabs/AlertsTab';
import ForecastTab from './tabs/ForecastTab';
import ProfileTab from './tabs/ProfileTab';

const Tab = createBottomTabNavigator();

export default function OwnerDashboardScreen({ session, onLogout }) {
  const [shop, setShop] = useState(null);
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [pendingOrderCount, setPendingOrderCount] = useState(0);

  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const isMountedRef = useRef(true);

  // ─── Fetch shared data ──────────────────────────────────────────────────────
  useEffect(() => {
    fetchMyShop();
  }, []);

  useEffect(() => {
    if (shop) {
      fetchProducts();
      fetchOrders();
      fetchAlerts();
      connectWebSocket();
    }
    return () => {
      isMountedRef.current = false;
      if (reconnectTimerRef.current) clearTimeout(reconnectTimerRef.current);
      if (socketRef.current) {
        try { socketRef.current.close(); } catch (e) {}
      }
    };
  }, [shop?.id]);

  useEffect(() => {
    const pending = orders.filter(o => o.status === 'pending' || o.status === 'pending_review').length;
    setPendingOrderCount(pending);
  }, [orders]);

  const authHeaders = () => ({
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${session.access_token}`,
  });

  const fetchMyShop = async () => {
    try {
      const res = await fetch(`${BACKEND_URL}/api/shops/my-shop`, {
        headers: authHeaders(),
      });
      if (res.ok) setShop(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchProducts = async () => {
    if (!shop) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/products/?shop_id=${shop.id}`, {
        headers: authHeaders(),
      });
      if (res.ok) setProducts(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchOrders = async () => {
    if (!shop) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/orders/?shop_id=${shop.id}`, {
        headers: authHeaders(),
      });
      if (res.ok) setOrders(await res.json());
    } catch (e) { console.error(e); }
  };

  const fetchAlerts = async () => {
    if (!shop) return;
    try {
      const res = await fetch(`${BACKEND_URL}/api/alerts/?shop_id=${shop.id}`, {
        headers: authHeaders(),
      });
      if (res.ok) setAlerts(await res.json());
    } catch (e) { console.error(e); }
  };

  // ─── WebSocket ──────────────────────────────────────────────────────────────
  const connectWebSocket = () => {
    if (!session?.user_id) return;
    const wsUrl = getWebSocketUrl(BACKEND_URL, session.user_id);
    const socket = new WebSocket(wsUrl);
    socketRef.current = socket;

    socket.onopen = () => {
      if (isMountedRef.current) setIsConnected(true);
    };
    socket.onmessage = (event) => {
      if (!isMountedRef.current) return;
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'new_order') {
          fetchOrders();
          Alert.alert('🛒 New Order!', 'A customer has placed a new order.');
        }
        if (data.type === 'low_stock') {
          fetchAlerts();
          fetchProducts();
          Alert.alert('⚠️ Low Stock Alert', data.message || 'A product is running low on stock.');
        }
        if (data.type === 'payment_success') {
          fetchOrders();
          Alert.alert('💰 Payment Received', 'A customer has paid for their order.');
        }
      } catch (e) {}
    };
    socket.onerror = () => {
      if (isMountedRef.current) setIsConnected(false);
    };
    socket.onclose = () => {
      if (isMountedRef.current) {
        setIsConnected(false);
        reconnectTimerRef.current = setTimeout(() => {
          if (isMountedRef.current) connectWebSocket();
        }, 3000);
      }
    };
  };

  // Shared props passed to all tab screens
  const sharedProps = {
    session,
    shop,
    products,
    orders,
    alerts,
    isConnected,
    onRefreshProducts: fetchProducts,
    onRefreshOrders: fetchOrders,
    onRefreshAlerts: fetchAlerts,
    onRefreshShop: fetchMyShop,
    onLogout,
  };

  if (!shop) {
    // No shop created yet — show setup screen
    return (
      <View style={sharedStyles.screen}>
        <View style={sharedStyles.header}>
          <Text style={sharedStyles.headerTitle}>🏪 Owner Dashboard</Text>
          <TouchableOpacity onPress={onLogout}>
            <Feather name="log-out" size={18} color="rgba(255,255,255,0.8)" />
          </TouchableOpacity>
        </View>
        <NoShopSetup session={session} onShopCreated={(s) => setShop(s)} />
      </View>
    );
  }

  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        headerShown: false,
        tabBarActiveTintColor: colors.tabActive,
        tabBarInactiveTintColor: colors.tabInactive,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.surfaceBorder,
          paddingBottom: 6,
          paddingTop: 6,
          height: 62,
        },
        tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
        tabBarIcon: ({ color, size }) => {
          const icons = {
            Orders: 'list',
            Inventory: 'package',
            Alerts: 'bell',
            Forecast: 'trending-up',
            Profile: 'user',
          };
          return <Feather name={icons[route.name]} size={size} color={color} />;
        },
      })}
    >
      <Tab.Screen
        name="Orders"
        options={{
          tabBarBadge: pendingOrderCount > 0 ? pendingOrderCount : undefined,
        }}
      >
        {() => <OrdersTab {...sharedProps} />}
      </Tab.Screen>
      <Tab.Screen name="Inventory">
        {() => <InventoryTab {...sharedProps} />}
      </Tab.Screen>
      <Tab.Screen name="Alerts">
        {() => <AlertsTab {...sharedProps} />}
      </Tab.Screen>
      <Tab.Screen name="Forecast">
        {() => <ForecastTab {...sharedProps} />}
      </Tab.Screen>
      <Tab.Screen name="Profile">
        {() => <ProfileTab {...sharedProps} />}
      </Tab.Screen>
    </Tab.Navigator>
  );
}

// ─── No Shop Setup ─────────────────────────────────────────────────────────────
function NoShopSetup({ session, onShopCreated }) {
  const [shopName, setShopName] = useState('');
  const [loading, setLoading] = useState(false);
  const { TextInput } = require('react-native');

  const createShop = async () => {
    if (!shopName.trim()) { Alert.alert('Error', 'Enter a shop name.'); return; }
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/shops/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${session.access_token}`,
        },
        body: JSON.stringify({ name: shopName.trim() }),
      });
      if (res.ok) {
        onShopCreated(await res.json());
      } else {
        Alert.alert('Error', 'Failed to create shop.');
      }
    } catch (e) {
      Alert.alert('Error', e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ flex: 1, padding: 24, justifyContent: 'center' }}>
      <View style={sharedStyles.card}>
        <Feather name="store" size={48} color={colors.primary} style={{ alignSelf: 'center', marginBottom: 12 }} />
        <Text style={[sharedStyles.title, { textAlign: 'center', marginBottom: 8 }]}>Create Your Shop</Text>
        <Text style={[sharedStyles.subtitle, { textAlign: 'center', marginBottom: 20 }]}>
          You haven't set up a shop yet. Enter your shop name to get started.
        </Text>
        <Text style={sharedStyles.label}>Shop Name *</Text>
        <TextInput
          style={sharedStyles.input}
          placeholder="My Grocery Store"
          value={shopName}
          onChangeText={setShopName}
        />
        <TouchableOpacity
          style={[sharedStyles.btnPrimary, loading && sharedStyles.btnDisabled]}
          onPress={createShop}
          disabled={loading}
        >
          <Text style={sharedStyles.btnPrimaryText}>
            {loading ? 'Creating...' : '🏪 Create Shop'}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}
