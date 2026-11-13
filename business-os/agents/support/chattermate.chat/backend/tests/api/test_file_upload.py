"""
Copyright 2024-2026 ChatterMate

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import pytest
import os
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from fastapi import FastAPI, status
from sqlalchemy.orm import Session

from app.api.file_upload import router, get_current_user_or_widget
from app.models.user import User
from app.models.organization import Organization
from app.core.config import settings
from tests.conftest import TestingSessionLocal, create_tables, engine
from app.database import Base


# Downloads are only ever served for chat attachments, which live at
# chat_attachments/<org_id>/<file> — the path's org segment is what authorizes
# the read, so every download test needs a real org id on both sides.
ORG_ID = "bab82aab-d095-46f8-bf16-da638671bcf4"
OTHER_ORG_ID = "11111111-2222-3333-4444-555555555555"
ATTACHMENT_KEY = f"chat_attachments/{ORG_ID}/file.txt"


def auth_user(org_id=ORG_ID):
    return {"type": "user", "user_id": "123", "org_id": org_id}


# Create test FastAPI app
test_app = FastAPI()
test_app.include_router(router, prefix="/api/v1/files")


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    """Local storage lives under ./uploads; give each test its own."""
    monkeypatch.chdir(tmp_path)
    folder = tmp_path / "uploads" / "chat_attachments" / ORG_ID
    folder.mkdir(parents=True)
    return folder


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(test_app)


@pytest.fixture
def db_session():
    """Create database session for testing"""
    create_tables()
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_organization(db_session):
    """Create test organization"""
    org = Organization(
        name="Test Organization",
        domain="test.com",
        timezone="UTC"
    )
    db_session.add(org)
    db_session.commit()
    db_session.refresh(org)
    return org


@pytest.fixture
def test_user(db_session, test_organization):
    """Create test user"""
    user = User(
        email="test@example.com",
        full_name="Test User",
        hashed_password="dummy_hash",
        is_active=True,
        organization_id=test_organization.id
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mock_request():
    """Create mock request object"""
    request = Mock()
    request.headers = {"origin": "https://example.com"}
    return request


class TestGetCurrentUserOrWidget:
    """Test authentication helper function"""
    
    @pytest.mark.asyncio
    async def test_get_current_user_success(self, db_session, test_user):
        """Test successful user authentication"""
        request = Mock()
        
        with patch('app.api.file_upload.get_current_user') as mock_get_user:
            mock_get_user.return_value = test_user
            
            result = await get_current_user_or_widget(request, db_session)
            
            assert result["type"] == "user"
            assert result["user_id"] == str(test_user.id)
            assert result["org_id"] == str(test_user.organization_id)
    
    @pytest.mark.asyncio
    async def test_get_current_user_widget_token(self, db_session):
        """Test widget authentication with conversation token"""
        request = Mock()
        
        with patch('app.api.file_upload.get_current_user') as mock_get_user, \
             patch('app.api.file_upload.verify_conversation_token') as mock_verify_token:
            
            # Mock user auth failure
            from fastapi import HTTPException
            mock_get_user.side_effect = HTTPException(status_code=401)
            
            # Mock successful token verification
            mock_verify_token.return_value = {
                "widget_id": "widget_123",
                "org_id": ORG_ID,
                "customer_id": "customer_789"
            }
            
            result = await get_current_user_or_widget(
                request, db_session, x_conversation_token="valid_token"
            )
            
            assert result["type"] == "widget"
            assert result["widget_id"] == "widget_123"
            assert result["org_id"] == ORG_ID
            assert result["customer_id"] == "customer_789"
    
    @pytest.mark.asyncio
    async def test_get_current_user_no_auth(self, db_session):
        """Test authentication failure"""
        request = Mock()
        
        with patch('app.api.file_upload.get_current_user') as mock_get_user:
            from fastapi import HTTPException
            mock_get_user.side_effect = HTTPException(status_code=401)
            
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user_or_widget(request, db_session)
            
            assert exc_info.value.status_code == 401
            assert "Authentication required" in str(exc_info.value.detail)


class TestDownloadFileLocal:
    """Test file download from local storage"""
    
    def test_download_file_local_success(self, client, uploads):
        (uploads / "file.txt").write_text("Test file content")
        with patch.object(settings, 'S3_FILE_STORAGE', False), \
             patch('app.api.file_upload.get_current_user_or_widget', return_value=auth_user()):
            response = client.get(f"/api/v1/files/download/{ATTACHMENT_KEY}")

        assert response.status_code == 200
        assert response.text == "Test file content"
        assert response.headers["content-type"] == "text/plain; charset=utf-8"

    def test_download_file_local_not_found(self, client, uploads):
        with patch.object(settings, 'S3_FILE_STORAGE', False), \
             patch('app.api.file_upload.get_current_user_or_widget', return_value=auth_user()):
            response = client.get(f"/api/v1/files/download/chat_attachments/{ORG_ID}/nonexistent.txt")

        assert response.status_code == 404
        assert "File not found" in response.json()["detail"]

    def test_an_svg_opened_directly_cannot_run_script(self, client, uploads):
        """Visitors upload SVGs; served from the API origin they must stay inert."""
        (uploads / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>')
        with patch.object(settings, 'S3_FILE_STORAGE', False), \
             patch('app.api.file_upload.get_current_user_or_widget', return_value=auth_user()):
            response = client.get(f"/api/v1/files/download/chat_attachments/{ORG_ID}/logo.svg")

        assert response.status_code == 200
        assert response.headers["content-security-policy"] == "script-src 'none'"
        assert response.headers["x-content-type-options"] == "nosniff"

    def test_download_file_local_without_auth(self, client):
        """Unauthenticated downloads are refused, not served anyway"""
        with patch.object(settings, 'S3_FILE_STORAGE', False), \
             patch('app.api.file_upload.get_current_user_or_widget') as mock_auth, \
             patch('os.path.exists') as mock_exists, \
             patch('builtins.open', create=True) as mock_open:

            from fastapi import HTTPException
            mock_auth.side_effect = HTTPException(status_code=401)
            mock_exists.return_value = True
            mock_open.return_value.__enter__.return_value.read.return_value = b"Test file content"

            response = client.get(f"/api/v1/files/download/{ATTACHMENT_KEY}")

            assert response.status_code == 401


class TestDownloadFileS3:
    """Test file download from S3 storage"""
    
    def test_download_file_s3_success(self, client):
        """Test successful file download from S3"""
        with patch.object(settings, 'S3_FILE_STORAGE', True), \
             patch.object(settings, 'S3_BUCKET', 'test-bucket'), \
             patch('app.api.file_upload.get_current_user_or_widget') as mock_auth, \
             patch('app.core.s3.get_s3_client') as mock_s3_client:
            
            mock_auth.return_value = auth_user()
            
            # Mock S3 client
            mock_client = Mock()
            mock_s3_client.return_value = mock_client
            
            # Mock successful head_object (file exists)
            mock_client.head_object.return_value = {}
            
            # Mock successful get_object
            mock_response = {
                'Body': Mock(),
                'ContentType': 'text/plain'
            }
            mock_response['Body'].read.side_effect = [b"Test content", b""]  # First chunk, then empty
            mock_client.get_object.return_value = mock_response
            
            response = client.get(f"/api/v1/files/download/{ATTACHMENT_KEY}")
            
            assert response.status_code == 200
            mock_client.head_object.assert_called_once_with(Bucket='test-bucket', Key=ATTACHMENT_KEY)
            mock_client.get_object.assert_called_once_with(Bucket='test-bucket', Key=ATTACHMENT_KEY)
            assert response.headers["content-security-policy"] == "script-src 'none'"
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["content-disposition"] == "inline; filename*=utf-8''file.txt"
    
    def test_download_file_s3_not_found(self, client):
        """Test S3 file download when file doesn't exist"""
        with patch.object(settings, 'S3_FILE_STORAGE', True), \
             patch.object(settings, 'S3_BUCKET', 'test-bucket'), \
             patch('app.api.file_upload.get_current_user_or_widget') as mock_auth, \
             patch('app.core.s3.get_s3_client') as mock_s3_client:
            
            mock_auth.return_value = auth_user()
            
            # Mock S3 client
            mock_client = Mock()
            mock_s3_client.return_value = mock_client
            
            # Mock NoSuchKey exception
            from botocore.exceptions import ClientError
            no_such_key_error = ClientError(
                error_response={'Error': {'Code': 'NoSuchKey'}},
                operation_name='HeadObject'
            )
            mock_client.exceptions = Mock()
            mock_client.exceptions.NoSuchKey = ClientError
            mock_client.head_object.side_effect = no_such_key_error
            
            response = client.get(f"/api/v1/files/download/chat_attachments/{ORG_ID}/nonexistent.txt")
            
            assert response.status_code == 404
            assert "File not found" in response.json()["detail"]
    
    def test_download_file_s3_client_error(self, client):
        """Test S3 file download with client creation error"""
        with patch.object(settings, 'S3_FILE_STORAGE', True), \
             patch('app.api.file_upload.get_current_user_or_widget') as mock_auth, \
             patch('app.core.s3.get_s3_client') as mock_s3_client:
            
            mock_auth.return_value = auth_user()
            mock_s3_client.side_effect = Exception("S3 client creation failed")
            
            response = client.get(f"/api/v1/files/download/{ATTACHMENT_KEY}")
            
            assert response.status_code == 500
            assert "Failed to create S3 client" in response.json()["detail"]
    
    def test_download_file_s3_get_object_error(self, client):
        """Test S3 file download with get_object error"""
        with patch.object(settings, 'S3_FILE_STORAGE', True), \
             patch.object(settings, 'S3_BUCKET', 'test-bucket'), \
             patch('app.api.file_upload.get_current_user_or_widget') as mock_auth, \
             patch('app.core.s3.get_s3_client') as mock_s3_client:
            
            mock_auth.return_value = auth_user()
            
            # Mock S3 client
            mock_client = Mock()
            mock_s3_client.return_value = mock_client
            
            # Mock successful head_object but failed get_object
            mock_client.head_object.return_value = {}
            
            # Mock exceptions properly
            from botocore.exceptions import ClientError
            mock_client.exceptions = Mock()
            mock_client.exceptions.NoSuchKey = ClientError
            mock_client.get_object.side_effect = Exception("S3 get_object failed")
            
            response = client.get(f"/api/v1/files/download/{ATTACHMENT_KEY}")
            
            assert response.status_code == 500
            assert "Failed to retrieve file from S3" in response.json()["detail"]


class TestDownloadFilePathHandling:
    """Test file path handling in download endpoint"""
    
    def test_download_file_path_with_uploads_prefix(self, client):
        """Test file path handling with /uploads/ prefix"""
        with patch.object(settings, 'S3_FILE_STORAGE', True), \
             patch.object(settings, 'S3_BUCKET', 'test-bucket'), \
             patch('app.api.file_upload.get_current_user_or_widget') as mock_auth, \
             patch('app.core.s3.get_s3_client') as mock_s3_client:
            
            mock_auth.return_value = auth_user()
            
            # Mock S3 client
            mock_client = Mock()
            mock_s3_client.return_value = mock_client
            mock_client.head_object.return_value = {}
            
            # Mock successful get_object
            mock_response = {
                'Body': Mock(),
                'ContentType': 'image/jpeg'
            }
            mock_response['Body'].read.side_effect = [b"image data", b""]
            mock_client.get_object.return_value = mock_response
            
            response = client.get(f"/api/v1/files/download//uploads/chat_attachments/{ORG_ID}/image.jpg")
            
            assert response.status_code == 200
            # The "/uploads/" prefix is stripped to get the storage key
            mock_client.head_object.assert_called_once_with(
                Bucket='test-bucket',
                Key=f'chat_attachments/{ORG_ID}/image.jpg'
            )
    
    def test_download_file_path_without_uploads_prefix(self, client):
        """Test file path handling without /uploads/ prefix"""
        with patch.object(settings, 'S3_FILE_STORAGE', True), \
             patch.object(settings, 'S3_BUCKET', 'test-bucket'), \
             patch('app.api.file_upload.get_current_user_or_widget') as mock_auth, \
             patch('app.core.s3.get_s3_client') as mock_s3_client:
            
            mock_auth.return_value = auth_user()
            
            # Mock S3 client
            mock_client = Mock()
            mock_s3_client.return_value = mock_client
            mock_client.head_object.return_value = {}
            
            # Mock successful get_object
            mock_response = {
                'Body': Mock(),
                'ContentType': 'application/pdf'
            }
            mock_response['Body'].read.side_effect = [b"pdf data", b""]
            mock_client.get_object.return_value = mock_response
            
            response = client.get(f"/api/v1/files/download/chat_attachments/{ORG_ID}/document.pdf")
            
            assert response.status_code == 200
            # Should use path as-is for S3 key
            mock_client.head_object.assert_called_once_with(
                Bucket='test-bucket', 
                Key=f'chat_attachments/{ORG_ID}/document.pdf'
            )


class TestDownloadFileAuthentication:
    """Test authentication scenarios for file download"""
    
    def test_download_file_with_jwt_auth(self, client, uploads):
        (uploads / "file.txt").write_text("Test content")
        with patch.object(settings, 'S3_FILE_STORAGE', False), \
             patch('app.api.file_upload.get_current_user_or_widget', return_value=auth_user()):
            response = client.get(f"/api/v1/files/download/{ATTACHMENT_KEY}",
                                  headers={"Authorization": "Bearer valid_jwt_token"})

        assert response.status_code == 200

    def test_download_file_with_conversation_token(self, client, uploads):
        (uploads / "file.txt").write_text("Test content")
        widget_auth = {"type": "widget", "widget_id": "widget_123", "org_id": ORG_ID, "customer_id": "customer_789"}
        with patch.object(settings, 'S3_FILE_STORAGE', False), \
             patch('app.api.file_upload.get_current_user_or_widget', return_value=widget_auth):
            response = client.get(f"/api/v1/files/download/{ATTACHMENT_KEY}",
                                  headers={"X-Conversation-Token": "valid_conversation_token"})

        assert response.status_code == 200


class TestDownloadFileContentTypes:
    """Test content type handling in file download"""
    
    @pytest.mark.parametrize("name, content_type", [
        ("image.jpg", "image/jpeg"),
        ("unknown.zzqq", "application/octet-stream"),
    ])
    def test_content_type_follows_the_file_name(self, client, uploads, name, content_type):
        (uploads / name).write_bytes(b"data")
        with patch.object(settings, 'S3_FILE_STORAGE', False), \
             patch('app.api.file_upload.get_current_user_or_widget', return_value=auth_user()):
            response = client.get(f"/api/v1/files/download/chat_attachments/{ORG_ID}/{name}")

        assert response.status_code == 200
        assert response.headers["content-type"] == content_type


class TestDownloadFileErrorHandling:
    """Test error handling in file download"""
    
    def test_download_file_general_exception(self, client):
        """An unexpected failure is a generic 500 that leaks no internals."""
        with patch.object(settings, 'S3_FILE_STORAGE', False), \
             patch('app.api.file_upload.get_current_user_or_widget', return_value=auth_user()), \
             patch('os.path.isfile', side_effect=Exception("Unexpected error at /srv/secret")):
            response = client.get(f"/api/v1/files/download/{ATTACHMENT_KEY}")

        assert response.status_code == 500
        assert response.json()["detail"] == "Failed to download file"

    def test_download_file_s3_head_object_general_error(self, client):
        """Test S3 head_object with general error (not NoSuchKey)"""
        with patch.object(settings, 'S3_FILE_STORAGE', True), \
             patch.object(settings, 'S3_BUCKET', 'test-bucket'), \
             patch('app.api.file_upload.get_current_user_or_widget') as mock_auth, \
             patch('app.core.s3.get_s3_client') as mock_s3_client:
            
            mock_auth.return_value = auth_user()
            
            # Mock S3 client
            mock_client = Mock()
            mock_s3_client.return_value = mock_client
            
            # Mock exceptions properly
            from botocore.exceptions import ClientError
            mock_client.exceptions = Mock()
            mock_client.exceptions.NoSuchKey = ClientError
            
            # Mock general exception in head_object (should continue to get_object)
            mock_client.head_object.side_effect = Exception("General S3 error")
            
            # Mock successful get_object
            mock_response = {
                'Body': Mock(),
                'ContentType': 'text/plain'
            }
            mock_response['Body'].read.side_effect = [b"Test content", b""]
            mock_client.get_object.return_value = mock_response
            
            response = client.get(f"/api/v1/files/download/{ATTACHMENT_KEY}")
            
            # Should still succeed because get_object works
            assert response.status_code == 200


class TestDownloadFileAuthorization:
    """The download path is authorization data, not just a lookup key"""

    def _serve(self, client, path, auth):
        with patch.object(settings, 'S3_FILE_STORAGE', False), \
             patch('app.api.file_upload.get_current_user_or_widget') as mock_auth, \
             patch('os.path.exists') as mock_exists, \
             patch('builtins.open', create=True) as mock_open:

            mock_auth.return_value = auth
            mock_exists.return_value = True
            mock_open.return_value.__enter__.return_value.read.return_value = b"secret"

            return client.get(f"/api/v1/files/download/{path}")

    def test_another_orgs_attachment_is_not_served(self, client):
        response = self._serve(
            client,
            f"chat_attachments/{OTHER_ORG_ID}/file.txt",
            auth_user(),
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "File not found"

    def test_widget_token_is_scoped_to_its_own_org(self, client):
        response = self._serve(
            client,
            f"chat_attachments/{OTHER_ORG_ID}/file.txt",
            {"type": "widget", "widget_id": "w1", "org_id": ORG_ID, "customer_id": "c1"},
        )

        assert response.status_code == 404

    @pytest.mark.parametrize("path", [
        "chat_attachments/../../etc/passwd",
        f"chat_attachments/{ORG_ID}/../../../etc/passwd",
        "uploads/../../etc/passwd",
        "etc/passwd",
        # Not an attachment: only chat_attachments is servable here.
        f"profile_pics/{ORG_ID}/avatar.png",
        # Missing the filename segment.
        f"chat_attachments/{ORG_ID}",
        # Org segment must be a real uuid.
        "chat_attachments/not-an-org/file.txt",
    ])
    def test_paths_outside_the_attachment_layout_are_refused(self, client, path):
        response = self._serve(client, path, auth_user())

        # Traversal attempts are normalized by the client and never match the
        # route at all, so assert the property that matters for every case:
        # nothing is served.
        assert response.status_code == 404
        assert b"secret" not in response.content

    def test_auth_without_an_org_gets_nothing(self, client):
        response = self._serve(
            client,
            ATTACHMENT_KEY,
            {"type": "user", "user_id": "123", "org_id": None},
        )

        assert response.status_code == 404
