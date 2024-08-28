"""
LDAP Backend for authentication.
"""
import ldap
from django.contrib.auth.models import User
from django.conf import settings
from pyvcloud_project.models import SppUser
from django.views.decorators.csrf import csrf_exempt


class LDAPBackend:
    """
    LDAP authentication backend.
    """
    @csrf_exempt
    def authenticate(self, request, username=None, password=None):
        """
        Authenticate the user.
        """
        user = None
        # Check if running in a test environment
        if settings.TEST:
            # Return None to bypass the authentication check
            return None

        try:  # signum + admin rights = is_superuser. admin = is_staff
            user = User.objects.get(username=username)
            if (user.is_staff and not user.check_password(password)) or \
                    (not user.is_staff and not check_credentials(username, password)):
                user = None
            else:
                create_spp_user(username, password, user)
        except User.DoesNotExist:
            if check_credentials(username, password):
                user = User(username=username, password="temppass")
                user.set_password(password)
                try:
                    user.email = get_ldap_email(username, password)[0]
                except Exception:
                    print('Could not get user email from LDAP')
                    user.email = None
                user.save()
                create_spp_user(username, password, user)
        finally:
            return user

    def get_user(self, user_id):
        """
        Get the user.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None


def create_spp_user(username, password, user):
    """
    Create or update SppUser.
    """
    spp_user = get_spp_user(user)
    ldap_groups = get_ldap_groups(username, password)

    if spp_user:
        spp_user.ldap_groups = ldap_groups
        spp_user.save()
    elif user:
        spp_user = SppUser()
        user = User.objects.get(username=username)
        update_spp_user(spp_user, user, ldap_groups)


def update_spp_user(spp_user, user, ldap_groups):
    """
    Update SppUser.
    """
    spp_user.user = user
    spp_user.ldap_groups = ldap_groups
    spp_user.save()


def get_spp_user(user):
    """
    Get SppUser.
    """
    try:
        return SppUser.objects.get(user=user)
    except SppUser.DoesNotExist:
        return None

@csrf_exempt
def check_credentials(username, password):
    """
    Check LDAP credentials.
    """
    ldap_username, ldap_client = set_ldap_credentials(username)
    try:
        # perform a synchronous bind
        print(ldap.__file__) 
        ldap_client.set_option(ldap.OPT_REFERRALS, 0)
        ldap_client.simple_bind_s(ldap_username, password)
        return True
    except Exception as e:
        print(str(e))
        return False
    except ldap.INVALID_CREDENTIALS:
        ldap_client.unbind()
        print('Wrong username or password')
        return False
    except ldap.SERVER_DOWN:
        print('LDAP server not available')
        return False


def get_ldap_email(username, password):
    """
    Get user email from LDAP.
    """
    email = _get_user_ldap_groups(username, password)
    if email is not None:
        email = email[0][1]['mail']
    return email


def get_ldap_groups(username, password):
    """
    Get LDAP groups.
    """
    ldap_groups = _get_user_ldap_groups(username, password, set_option=True)
    if ldap_groups is not None:
        ldap_groups = [group.decode() for group in
                       ldap_groups[0][1]['memberOf']]
        ldap_groups = ','.join(ldap_groups)
    return ldap_groups


def _get_user_ldap_groups(username, password, set_option=False):
    """
    Get user LDAP groups.
    """
    ldap_username, ldap_client = set_ldap_credentials(
        username, set_option=set_option)
    try:
        ldap_client.simple_bind_s(ldap_username, password)
        base_dn = "dc=ericsson,dc=se"
        search_scope = ldap.SCOPE_SUBTREE
        search_filter = "(mailNickname=" + username + ")"
        ldap_result_id = ldap_client.search(
            base_dn, search_scope, search_filter)
        _, r_data = ldap_client.result(ldap_result_id, 0)
        return r_data
    except Exception:
        return None


def set_ldap_credentials(username, set_option=False):
    """
    Set LDAP credentials.
    """
    if set_option:
        ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
    ldap_username = f'{username}@ericsson.se'
    ldap_server = 'ldaps://eriseli05.ericsson.se:3269'
    print("This is LDAP")
    print(ldap_server)
    ldap_client = ldap.initialize(ldap_server)

    return ldap_username, ldap_client
