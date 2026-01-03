ERROR_CODES = {
    # General
    "NO_DATA_PROVIDED": {"code": 1001, "message": "No data provided"},
    "INVALID_REQUEST": {"code": 1002, "message": "Invalid request"},
    "INTERNAL_SERVER_ERROR": {"code": 1003, "message": "Internal server error"},
    
    # User errors
    "USER_NOT_FOUND": {"code": 2001, "message": "User not found"},
    "USER_CREATION_FAILED": {"code": 2002, "message": "Could not create user"},
    "USER_UPDATE_FAILED": {"code": 2003, "message": "Could not update user"},
    "USER_DELETE_FAILED": {"code": 2004, "message": "Could not delete user"},
    
    # Friend errors
    "SELF_FRIEND_REQUEST": {"code": 2005, "message": "You cannot send a friend request to yourself"},
    "FRIEND_REQUEST_EXISTS": {"code": 2006, "message": "Friend request already sent"},
    "FRIEND_REQUEST_NOT_FOUND": {"code": 2007, "message": "No friend request from this user"},
    "FRIEND_NOT_FOUND": {"code": 2008, "message": "Friend not found"},
    "FRIEND_ALREADY_ADDED": {"code": 2009, "message": "Friend is already in your list"},
    
    # Team errors
    "NO_PLAYERS_PROVIDED": {"code": 3001, "message": "No players provided"},
    "TEAM_SIZE_EXCEEDED": {"code": 3002, "message": "Team cannot have more than the maximum allowed players"},
    "INVALID_POSITION": {"code": 3003, "message": "Invalid position for player"},
    "TEAM_NOT_FOUND": {"code": 3004, "message": "Team not found"},
    "TEAM_CREATION_FAILED": {"code": 3005, "message": "Could not create team"},
    "TEAM_UPDATE_FAILED": {"code": 3006, "message": "Could not update team"},
    "TEAM_DELETE_FAILED": {"code": 3007, "message": "Could not delete team"},
    "TEAM_INVITE_EXISTS": {"code": 3008, "message": "Team invite already sent"},
    "TEAM_INVITE_NOT_FOUND": {"code": 3009, "message": "No invite found for this team"},
    "PLAYER_ALREADY_IN_TEAM": {"code": 3010, "message": "User is already in the team"},

    # Event errors
    "EVENT_NOT_FOUND": {"code": 3101, "message": "Event not found"},
    "EVENT_CREATION_FAILED": {"code": 3102, "message": "Could not create event"},
    "EVENT_UPDATE_FAILED": {"code": 3103, "message": "Could not update event"},
    "EVENT_DELETE_FAILED": {"code": 3104, "message": "Could not delete event"},
    "EVENT_LINK_REQUIRED": {"code": 3105, "message": "An event must be linked to the team"},
    "INVALID_EVENT_DATE": {"code": 3106, "message": "Invalid event date format"},

    # Player "Going" Status errors
    "INVALID_GOING_STATUS": {"code": 3201, "message": "Invalid player status. Must be 'yes', 'no', 'maybe', or 'no response'"},
    "PLAYER_STATUS_UPDATE_FAILED": {"code": 3202, "message": "Could not update player status"},
    
    # Auth errors
    "TOKEN_CREATION_FAILED": {"code": 4001, "message": "Could not create token"},
    "TOKEN_DECODE_FAILED": {"code": 4002, "message": "Could not decode token"},
    "TOKEN_NOT_FOUND": {"code": 4003, "message": "No token provided"},
    "INVALID_TOKEN": {"code": 4004, "message": "Token is invalid or expired"},
    "USER_CONTEXT_FAILED": {"code": 4005, "message": "Could not attach user context"},
    
    # Pending Team errors
    "PENDING_TEAM_NOT_FOUND": {"code": 5001, "message": "Pending team not found"},
    "PENDING_TEAM_CREATION_FAILED": {"code": 5002, "message": "Could not create pending team"},
    "PENDING_TEAM_UPDATE_FAILED": {"code": 5003, "message": "Could not update pending team"},
    "PENDING_TEAM_DELETE_FAILED": {"code": 5004, "message": "Could not delete pending team"},
    "PENDING_TEAM_ALREADY_EXISTS": {"code": 5005, "message": "A pending team already exists for this user"},
    "PENDING_TEAM_INVITE_EXISTS": {"code": 5006, "message": "Pending team invite already sent"},
    "PENDING_TEAM_INVITE_NOT_FOUND": {"code": 5007, "message": "No invite found for this pending team"},
    "PLAYER_ALREADY_IN_PENDING_TEAM": {"code": 5008, "message": "User is already in the pending team"},
    "TEAM_CONVERSION_FAILED": {"code": 5009, "message": "Could not convert pending team to full team"},
    "PENDING_TEAM_EMPTY": {"code": 5010, "message": "Cannot convert pending team without players"},
    
    # Firestore errors
    "FIRESTORE_READ_FAILED": {"code": 6001, "message": "Could not read data from Firestore"},
    "FIRESTORE_WRITE_FAILED": {"code": 6002, "message": "Could not write data to Firestore"},
    "FIRESTORE_UPDATE_FAILED": {"code": 6003, "message": "Could not update data in Firestore"},
    "FIRESTORE_DELETE_FAILED": {"code": 6004, "message": "Could not delete data from Firestore"},

    # Notifications errors
    "NOTIFICATION_SEND_FAILED": {"code": 7001, "message": "Failed to send notification"},
    "NOTIFICATION_NO_FCM_TOKEN": {"code": 7002, "message": "User does not have a valid FCM token"},
    "NOTIFICATION_USER_NOT_FOUND": {"code": 7003, "message": "User not found while sending notification"},
    "NOTIFICATION_PAYLOAD_INVALID": {"code": 7004, "message": "Invalid notification payload"},

    # Messaging errors
    "MESSAGING_SEND_FAILED": {"code": 8001, "message": "Failed to send message"},
    "MESSAGING_NO_FCM_TOKEN": {"code": 8002, "message": "User does not have a valid FCM token"},
    "MESSAGING_USER_NOT_FOUND": {"code": 8003, "message": "User not found while sending message"},
    "MESSAGING_PAYLOAD_INVALID": {"code": 8004, "message": "Invalid message payload"},
    "MESSAGING_FIELDS_NOT_FOUND": {"code": 8005, "message": "Missing required fields in notification"},

    # Direct messaging errors
    "DIRECT_MESSAGE_RECIPIENT_REQUIRED": {"code": 8101, "message": "Recipient ID is required"},
    "DIRECT_MESSAGE_TEXT_REQUIRED": {"code": 8102, "message": "Message text is required"},
    "DIRECT_MESSAGE_FORBIDDEN": {"code": 8103, "message": "You do not have access to this conversation"},
    "DIRECT_MESSAGE_NOT_FOUND": {"code": 8104, "message": "Conversation not found"}
}
