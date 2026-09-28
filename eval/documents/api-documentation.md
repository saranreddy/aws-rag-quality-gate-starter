# CloudSync API Documentation

## Authentication

All API requests require authentication using an API key. Generate your API key in the CloudSync dashboard under Settings > API Keys.

Include your API key in the `Authorization` header:

```
Authorization: Bearer YOUR_API_KEY
```

## Base URL

```
https://api.cloudsync.com/v1
```

## Rate Limits

- Free plan: 100 requests per hour
- Professional plan: 1,000 requests per hour
- Enterprise plan: 10,000 requests per hour

When you exceed the rate limit, you'll receive a `429 Too Many Requests` response.

## Endpoints

### Upload File

Upload a file to CloudSync.

**Endpoint**: `POST /files/upload`

**Request**:
```json
{
  "filename": "document.pdf",
  "folder_path": "/team/projects",
  "content": "base64_encoded_content"
}
```

**Response**:
```json
{
  "file_id": "file_abc123",
  "filename": "document.pdf",
  "size_bytes": 1048576,
  "created_at": "2024-01-15T10:30:00Z",
  "url": "https://cloudsync.com/files/file_abc123"
}
```

### Download File

Download a file by ID.

**Endpoint**: `GET /files/{file_id}/download`

**Response**: Binary file content with appropriate Content-Type header

### List Files

List all files in your account or a specific folder.

**Endpoint**: `GET /files`

**Query Parameters**:
- `folder_path` (optional): Filter by folder path
- `limit` (optional): Number of results (default: 50, max: 500)
- `offset` (optional): Pagination offset

**Response**:
```json
{
  "files": [
    {
      "file_id": "file_abc123",
      "filename": "document.pdf",
      "size_bytes": 1048576,
      "created_at": "2024-01-15T10:30:00Z",
      "modified_at": "2024-01-15T11:45:00Z"
    }
  ],
  "total_count": 150,
  "has_more": true
}
```

### Delete File

Delete a file (moves to trash).

**Endpoint**: `DELETE /files/{file_id}`

**Response**:
```json
{
  "success": true,
  "deleted_at": "2024-01-15T12:00:00Z",
  "trash_retention_days": 90
}
```

### Create Shared Link

Create a public sharing link for a file.

**Endpoint**: `POST /files/{file_id}/share`

**Request**:
```json
{
  "expires_in_days": 7,
  "password_protected": false,
  "allow_download": true
}
```

**Response**:
```json
{
  "share_url": "https://cloudsync.com/s/abc123xyz",
  "expires_at": "2024-01-22T12:00:00Z"
}
```

## Error Handling

The API uses standard HTTP status codes:

- `200 OK`: Request succeeded
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Invalid or missing API key
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server error

Error response format:
```json
{
  "error": {
    "code": "invalid_request",
    "message": "The 'filename' parameter is required"
  }
}
```

## Webhooks

Configure webhooks to receive real-time notifications of events.

**Available Events**:
- `file.uploaded`: File uploaded
- `file.deleted`: File deleted
- `file.shared`: File shared
- `folder.created`: Folder created

Configure webhooks in Settings > Webhooks. Webhook payloads are sent as POST requests with event data in JSON format.

## SDKs

Official SDKs available:
- Python: `pip install cloudsync-sdk`
- Node.js: `npm install cloudsync`
- Ruby: `gem install cloudsync`
- Go: `go get github.com/cloudsync/cloudsync-go`
