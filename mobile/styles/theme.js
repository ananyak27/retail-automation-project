import { StyleSheet } from 'react-native';

// ─────────────────────────────────────────────────
// Design tokens (mirrors the web CSS variables)
// ─────────────────────────────────────────────────
export const colors = {
  primary: '#6366f1',
  primaryLight: '#eef2ff',
  secondary: '#10b981',
  secondaryLight: '#d1fae5',
  error: '#ef4444',
  errorLight: '#fee2e2',
  warning: '#f59e0b',
  warningLight: '#fef3c7',
  surface: '#ffffff',
  surfaceLight: '#f8fafc',
  surfaceBorder: '#e2e8f0',
  textPrimary: '#1e293b',
  textSecondary: '#64748b',
  textMuted: '#94a3b8',
  headerBg: '#1e1b4b',
  headerText: '#ffffff',
  tabActive: '#6366f1',
  tabInactive: '#94a3b8',
};

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
};

// ─────────────────────────────────────────────────
// Shared / reusable styles
// ─────────────────────────────────────────────────
export const sharedStyles = StyleSheet.create({
  // Containers
  flex1: { flex: 1 },
  flexRow: { flexDirection: 'row' },
  flexCenter: { alignItems: 'center', justifyContent: 'center' },
  screen: {
    flex: 1,
    backgroundColor: colors.surfaceLight,
  },

  // Cards
  card: {
    backgroundColor: colors.surface,
    borderRadius: radius.md,
    padding: 16,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 3,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
  },

  // Typography
  title: {
    fontSize: 22,
    fontWeight: '800',
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: 14,
    color: colors.textSecondary,
    marginTop: 4,
  },
  label: {
    fontSize: 13,
    fontWeight: '600',
    color: colors.textPrimary,
    marginBottom: 6,
  },
  bodyText: {
    fontSize: 14,
    color: colors.textPrimary,
  },
  smallText: {
    fontSize: 12,
    color: colors.textSecondary,
  },
  boldText: {
    fontWeight: '700',
  },

  // Inputs
  input: {
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.surfaceBorder,
    borderRadius: radius.sm,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 14,
    color: colors.textPrimary,
    marginBottom: 14,
  },

  // Buttons
  btnPrimary: {
    backgroundColor: colors.primary,
    borderRadius: radius.sm,
    paddingVertical: 14,
    alignItems: 'center',
    marginBottom: 10,
  },
  btnPrimaryText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 15,
  },
  btnSecondary: {
    backgroundColor: 'transparent',
    borderWidth: 1.5,
    borderColor: colors.primary,
    borderRadius: radius.sm,
    paddingVertical: 12,
    alignItems: 'center',
    marginBottom: 10,
  },
  btnSecondaryText: {
    color: colors.primary,
    fontWeight: '700',
    fontSize: 14,
  },
  btnDanger: {
    backgroundColor: colors.error,
    borderRadius: radius.sm,
    paddingVertical: 12,
    alignItems: 'center',
  },
  btnDangerText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 14,
  },
  btnDisabled: {
    opacity: 0.5,
  },

  // Badges / status chips
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 20,
    alignSelf: 'flex-start',
  },
  badgeText: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'capitalize',
  },

  // Header
  header: {
    backgroundColor: colors.headerBg,
    paddingTop: 48,
    paddingBottom: 16,
    paddingHorizontal: 20,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '800',
    color: colors.headerText,
  },
  headerSubtitle: {
    fontSize: 11,
    color: 'rgba(255,255,255,0.7)',
  },

  // Error / Info boxes
  errorBox: {
    backgroundColor: colors.errorLight,
    borderLeftWidth: 4,
    borderLeftColor: colors.error,
    borderRadius: radius.sm,
    padding: 12,
    marginBottom: 14,
  },
  errorText: {
    color: colors.error,
    fontSize: 13,
    fontWeight: '500',
  },
  infoBox: {
    backgroundColor: colors.secondaryLight,
    borderLeftWidth: 4,
    borderLeftColor: colors.secondary,
    borderRadius: radius.sm,
    padding: 12,
    marginBottom: 14,
  },
  infoText: {
    color: '#065f46',
    fontSize: 13,
  },
  warningBox: {
    backgroundColor: colors.warningLight,
    borderLeftWidth: 4,
    borderLeftColor: colors.warning,
    borderRadius: radius.sm,
    padding: 12,
    marginBottom: 14,
  },
  warningText: {
    color: '#92400e',
    fontSize: 13,
    fontWeight: '500',
  },

  // Divider
  divider: {
    height: 1,
    backgroundColor: colors.surfaceBorder,
    marginVertical: 12,
  },

  // Tab bar item text
  tabLabel: {
    fontSize: 11,
    fontWeight: '600',
  },

  // Section header row
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.textPrimary,
  },

  // Centered placeholder
  emptyContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  emptyText: {
    fontSize: 15,
    color: colors.textSecondary,
    textAlign: 'center',
    marginTop: 12,
  },
});

/**
 * Returns a status badge color pair { bg, text } for a given order/payment status.
 */
export const getStatusColors = (status) => {
  switch (status) {
    case 'approved':
    case 'paid':
      return { bg: '#d4edda', text: '#155724' };
    case 'rejected':
      return { bg: '#f8d7da', text: '#721c24' };
    case 'pending':
    case 'pending_review':
      return { bg: '#fff3cd', text: '#856404' };
    case 'cash_pending':
      return { bg: '#d4edda', text: '#155724' };
    default:
      return { bg: colors.surfaceLight, text: colors.textSecondary };
  }
};
