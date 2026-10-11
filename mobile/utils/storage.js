import AsyncStorage from '@react-native-async-storage/async-storage';

/**
 * Save session to AsyncStorage (replaces web sessionStorage)
 */
export const saveSession = async (session) => {
  try {
    await AsyncStorage.setItem('retail_session', JSON.stringify(session));
  } catch (e) {
    console.error('Failed to save session:', e);
  }
};

/**
 * Load session from AsyncStorage
 */
export const loadSession = async () => {
  try {
    const stored = await AsyncStorage.getItem('retail_session');
    return stored ? JSON.parse(stored) : null;
  } catch (e) {
    console.error('Failed to load session:', e);
    return null;
  }
};

/**
 * Remove session from AsyncStorage
 */
export const clearSession = async () => {
  try {
    await AsyncStorage.removeItem('retail_session');
  } catch (e) {
    console.error('Failed to clear session:', e);
  }
};

/**
 * Save any key-value pair (replaces localStorage)
 */
export const setItem = async (key, value) => {
  try {
    await AsyncStorage.setItem(key, String(value));
  } catch (e) {
    console.error(`Failed to set item ${key}:`, e);
  }
};

/**
 * Get a stored item (replaces localStorage.getItem)
 */
export const getItem = async (key) => {
  try {
    return await AsyncStorage.getItem(key);
  } catch (e) {
    console.error(`Failed to get item ${key}:`, e);
    return null;
  }
};

/**
 * Remove a stored item
 */
export const removeItem = async (key) => {
  try {
    await AsyncStorage.removeItem(key);
  } catch (e) {
    console.error(`Failed to remove item ${key}:`, e);
  }
};
