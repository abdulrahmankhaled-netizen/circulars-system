"""
كل الثوابت والحالات (Constants & States) — مكان واحد لكل شيء.
"""


# ============================================================
#  ROLES — الأدوار
# ============================================================
ROLES = {
    "admin": {
        "label_ar": "مدير النظام",
        "description": "صلاحيات كاملة على كل شيء",
        "permissions": ["*"],
    },
    "manager": {
        "label_ar": "مدير",
        "description": "إدارة عامة + موافقات",
        "permissions": [
            "requests.*", "contracts.*", "missions.*",
            "suppliers.*", "equipment.*", "invoices.*",
            "reports.*",
            "dashboard.view", "users.view",
        ],
    },
    "transport_manager": {
        "label_ar": "مدير النقل",
        "description": "إدارة فريق النقل والمهام",
        "permissions": [
            "requests.*", "missions.*", "dashboard.view",
        ],
    },
    "transport_user": {
        "label_ar": "موظف نقل",
        "description": "إنشاء طلبات ومهام",
        "permissions": [
            "requests.create", "requests.edit", "requests.view",
            "missions.create", "missions.edit", "missions.view",
            "dashboard.view",
        ],
    },
    "finance": {
        "label_ar": "المالية",
        "description": "الفواتير والمدفوعات",
        "permissions": [
            "invoices.*", "contracts.view",
            "suppliers.view", "missions.view",
            "dashboard.view",
        ],
    },
    "auditor": {
        "label_ar": "مدقق",
        "description": "قراءة فقط",
        "permissions": ["*.view"],
    },
}


# ============================================================
#  EQUIPMENT TYPES — أنواع المعدات
# ============================================================
EQUIPMENT_TYPES = [
    {"key": "flatbed_3",         "name_ar": "سطحه 3 طن",            "name_en": "3 TON half down"},
    {"key": "flatbed_6",         "name_ar": "سطحه 6 طن",            "name_en": "Flatbed 6T"},
    {"key": "flatbed_6_double",  "name_ar": "سطحه 6 طن دبل",        "name_en": "6 TON Double Towing"},
    {"key": "flatbed_6_full",    "name_ar": "سطحه 6 طن كامل",       "name_en": "6 TON Full Down"},
    {"key": "flatbed_6_half",    "name_ar": "سطحه 6 طن نص",         "name_en": "6 Ton half down"},
    {"key": "flatbed_7",         "name_ar": "سطحه 7 طن",            "name_en": "Flatbed 7T"},
    {"key": "flatbed_10",        "name_ar": "سطحه 10 طن",           "name_en": "Flatbed 10T"},
    {"key": "flatbed_13",        "name_ar": "سطحه 13 طن",           "name_en": "Flatbed 13T"},
    {"key": "flatbed_13_double", "name_ar": "سطحه 13 طن دبل",       "name_en": "13 TON Double Towing"},
    {"key": "flatbed_25",        "name_ar": "سطحه 25 طن",           "name_en": "Flatbed 25T"},
    {"key": "flatbed_25_double", "name_ar": "سطحه 25 طن دبل",       "name_en": "25 TON Double Towing"},
    {"key": "mobile_crane_70",   "name_ar": "موبايل كرين 70 طن",     "name_en": "Mobile Crane 70T"},
    {"key": "mobile_crane_80",   "name_ar": "موبايل كرين 80 طن",     "name_en": "Mobile Crane 80T"},
    {"key": "mobile_crane_100",  "name_ar": "موبايل كرين 100 طن",   "name_en": "Mobile Crane 100T"},
    {"key": "rucker",            "name_ar": "راكر",                  "name_en": "Rucker"},
    {"key": "lowbed",            "name_ar": "لوبيد",                 "name_en": "Lowbed"},
    {"key": "wrecker_heavy",     "name_ar": "ونش ثقيل",              "name_en": "Wrecker heavy"},
    {"key": "wrecker_light",     "name_ar": "ونش خفيف",              "name_en": "Wrecker light"},
]


# ============================================================
#  WORKFLOW STATES
# ============================================================
REQUEST_STATES = [
    ("draft",        "مسودة",           "secondary", False),
    ("submitted",    "بانتظار المراجعة", "info",      False),
    ("under_review", "قيد المراجعة",     "primary",   False),
    ("approved",     "معتمد",           "success",   False),
    ("rejected",     "مرفوض",           "danger",    True),
    ("contracted",   "تم التعاقد",       "dark",      False),
    ("fulfilled",    "منفّذ",            "success",   True),
    ("cancelled",    "ملغي",             "secondary", True),
]

CONTRACT_STATES = [
    ("draft",             "مسودة",           "secondary", False),
    ("pending_signature", "بانتظار التوقيع", "warning",   False),
    ("active",            "نشط",             "success",   False),
    ("expiring",          "قارب الانتهاء",   "warning",   False),
    ("expired",           "منتهي",           "danger",    True),
    ("terminated",        "ملغى",            "dark",      True),
]

MISSION_STATES = [
    ("draft",       "مسودة",        "secondary", False),
    ("assigned",    "مُعيّنة",       "info",      False),
    ("in_progress", "قيد التنفيذ",  "primary",   False),
    ("completed",   "مكتملة",        "success",   False),
    ("verified",    "تم التحقق",     "success",   False),
    ("invoiced",    "مفوترة",        "dark",      False),
    ("paid",        "مدفوعة",        "success",   True),
    ("cancelled",   "ملغاة",         "danger",    True),
    ("failed",      "فاشلة",         "danger",    True),
]

INVOICE_STATES = [
    ("draft",     "مسودة",         "secondary", False),
    ("submitted", "مُقدّمة",        "info",      False),
    ("approved",  "معتمدة",         "primary",   False),
    ("paid",      "مدفوعة",         "success",   True),
    ("disputed",  "متنازع عليها",  "danger",    False),
    ("cancelled", "ملغاة",          "secondary", True),
]


# ============================================================
#  TRANSITIONS
# ============================================================
REQUEST_TRANSITIONS = [
    {
        "action": "submit",
        "label_ar": "تقديم الطلب",
        "from_states": ["draft"],
        "to_state": "submitted",
        "roles": ["transport_user", "transport_manager", "admin"],
        "requires_comment": False,
        "notify_roles": ["transport_manager", "manager", "admin"],
    },
    {
        "action": "start_review",
        "label_ar": "بدء المراجعة",
        "from_states": ["submitted"],
        "to_state": "under_review",
        "roles": ["transport_manager", "manager", "admin"],
        "requires_comment": False,
        "notify_roles": [],
    },
    {
        "action": "approve",
        "label_ar": "اعتماد",
        "from_states": ["under_review", "submitted"],
        "to_state": "approved",
        "roles": ["manager", "admin"],
        "requires_comment": False,
        "notify_roles": ["transport_manager", "finance"],
    },
    {
        "action": "reject",
        "label_ar": "رفض",
        "from_states": ["under_review", "submitted"],
        "to_state": "rejected",
        "roles": ["manager", "admin"],
        "requires_comment": True,
        "notify_roles": ["transport_manager"],
    },
    {
        "action": "mark_contracted",
        "label_ar": "تم التعاقد",
        "from_states": ["approved"],
        "to_state": "contracted",
        "roles": ["manager", "admin"],
        "requires_comment": False,
        "notify_roles": ["transport_manager"],
    },
    {
        "action": "fulfill",
        "label_ar": "تأكيد التنفيذ",
        "from_states": ["contracted"],
        "to_state": "fulfilled",
        "roles": ["transport_manager", "admin"],
        "requires_comment": False,
        "notify_roles": ["manager"],
    },
    {
        "action": "cancel",
        "label_ar": "إلغاء",
        "from_states": ["draft", "submitted", "under_review", "approved"],
        "to_state": "cancelled",
        "roles": ["transport_manager", "manager", "admin"],
        "requires_comment": True,
        "notify_roles": [],
    },
]

CONTRACT_TRANSITIONS = [
    {
        "action": "send_for_signature",
        "label_ar": "إرسال للتوقيع",
        "from_states": ["draft"],
        "to_state": "pending_signature",
        "roles": ["manager", "admin"],
        "requires_comment": False,
        "notify_roles": [],
    },
    {
        "action": "activate",
        "label_ar": "تفعيل",
        "from_states": ["pending_signature", "draft"],
        "to_state": "active",
        "roles": ["manager", "admin"],
        "requires_comment": False,
        "notify_roles": ["transport_manager", "finance"],
    },
    {
        "action": "terminate",
        "label_ar": "إنهاء",
        "from_states": ["active", "expiring"],
        "to_state": "terminated",
        "roles": ["admin"],
        "requires_comment": True,
        "notify_roles": ["finance"],
    },
]

MISSION_TRANSITIONS = [
    {
        "action": "assign",
        "label_ar": "تعيين",
        "from_states": ["draft"],
        "to_state": "assigned",
        "roles": ["transport_manager", "transport_user", "admin"],
        "requires_comment": False,
        "notify_roles": [],
    },
    {
        "action": "start",
        "label_ar": "بدء التنفيذ",
        "from_states": ["assigned"],
        "to_state": "in_progress",
        "roles": ["transport_manager", "transport_user", "admin"],
        "requires_comment": False,
        "notify_roles": [],
    },
    {
        "action": "complete",
        "label_ar": "إكمال",
        "from_states": ["in_progress"],
        "to_state": "completed",
        "roles": ["transport_manager", "transport_user", "admin"],
        "requires_comment": False,
        "notify_roles": ["transport_manager"],
    },
    {
        "action": "verify",
        "label_ar": "التحقق",
        "from_states": ["completed"],
        "to_state": "verified",
        "roles": ["transport_manager", "manager", "admin"],
        "requires_comment": False,
        "notify_roles": ["finance"],
    },
    {
        "action": "fail",
        "label_ar": "فشل",
        "from_states": ["assigned", "in_progress"],
        "to_state": "failed",
        "roles": ["transport_manager", "admin"],
        "requires_comment": True,
        "notify_roles": ["manager"],
    },
    {
        "action": "cancel",
        "label_ar": "إلغاء",
        "from_states": ["draft", "assigned"],
        "to_state": "cancelled",
        "roles": ["transport_manager", "manager", "admin"],
        "requires_comment": True,
        "notify_roles": [],
    },
]


# ============================================================
#  PRIORITIES & PAYMENT
# ============================================================
PRIORITIES = [
    ("low",    "منخفضة", "secondary"),
    ("normal", "عادية",  "info"),
    ("high",   "عالية",  "warning"),
    ("urgent", "عاجلة",  "danger"),
]

PAYMENT_STATUSES = [
    ("pending",   "معلّق",         "warning"),
    ("paid",      "مدفوع",         "success"),
    ("stored",    "تخزين - مضمون", "info"),
    ("cancelled", "ملغي",          "secondary"),
]


# ============================================================
#  SUPPLIER STATUSES
# ============================================================
SUPPLIER_STATUSES = [
    ("active",      "نشط",     "success"),
    ("suspended",   "موقوف",   "warning"),
    ("blacklisted", "محظور",   "danger"),
]


# ============================================================
#  Helpers
# ============================================================
def get_label(collection, key, default="—"):
    """يعيد التسمية العربية من قائمة tuples."""
    for item in collection:
        if item[0] == key:
            return item[1]
    return default


def get_color(collection, key, default="secondary"):
    for item in collection:
        if item[0] == key:
            return item[2] if len(item) > 2 else default
    return default