"""
Constants used across the entire project.
"""



# Max number of participants a single group conversation can have.
# Enforced in create_group_conversation and add_participant so both
# entry points share the same limit.
MAX_GROUP_PARTICIPANTS = 256


# DOMAIN RULES
# Max length of a chat message body. Enforced in the send_message
# service so every transport (web view, DRF API, any future caller)
# shares the exact same limit — a single source of truth.
MAX_MESSAGE_LENGTH = 5000


# REALTIME BROADCASTS
PRESENCE_GROUP = 'presence_broadcasts'
BROADCAST_READ_RECEIPT = 'broadcast_read_receipt'
BROADCAST_NEW_MESSAGE = 'broadcast_new_message'
BROADCAST_TYPING = 'broadcast_typing'
# Channel-layer "type" for forcing a WebSocket closed when its
# DeviceSession is revoked. Must match a handler method name on every
# consumer that can be tied to a device session (chat.ChatConsumer,
# accounts.PresenceConsumer) — see device_session_group() below.
BROADCAST_SESSION_REVOKED = 'broadcast_session_revoked'


# SOCKET EVENTS
BROADCAST_PRESENCE = 'presence'
READ_RECEIPT = 'read_receipt'
TYPING = 'typing'
NEW_MESSAGE = 'message.new'
BROADCAST_PRESENCE_UPDATE = 'presence.update'
SESSION_REVOKED = 'session.revoked'


def device_session_group(session_id):
    """
    Channels group name for a single DeviceSession. Every WebSocket
    connection authenticated with a JWT carrying that session's "sid"
    claim joins this group (see apps.chat.consumers.ChatConsumer and
    apps.accounts.consumers.PresenceConsumer). Revoking the session
    (apps.accounts.services.realtime.broadcast_session_revoked) sends
    a message to this group so every open connection tied to that
    device is force-closed immediately, instead of staying open until
    its access token happens to expire on its own.
    """
    return f'device_session_{session_id}'