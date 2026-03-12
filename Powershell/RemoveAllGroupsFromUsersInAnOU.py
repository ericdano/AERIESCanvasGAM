# -*- coding: utf-8 -*-
"""
This script removes all group memberships for all user objects within a
specified Active Directory (AD) Organizational Unit (OU).

Prerequisites:
1.  The 'pyad' library must be installed:
    pip install pyad
2.  The 'pywin32' extensions must be installed:
    pip install pypiwin32
3.  The script must be run on a domain-joined Windows machine.
4.  The script must be executed by a domain user with permissions to:
    - Read users in the target OU.
    - Modify group memberships.

SAFETY:
This script runs in DRY_RUN mode by default. It will only report the
actions it would take. To execute the changes, you must edit the script
and set the DRY_RUN variable to False.

The script will NOT remove users from the 'Domain Users' group, as this
is a critical group for basic account functionality.
"""

from pyad import aduser, adcontainer, adgroup, pyad_exceptions

# --- PLEASE CONFIGURE THESE VARIABLES ---

# The Distinguished Name (DN) of the OU you want to target.
# Example: "OU=Sales,OU=Users,DC=yourdomain,DC=com"
TARGET_OU_DN = "OU=Students,OU=AHS,OU=Graduated 2025,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us"

# --- SAFETY SWITCH ---
# Set to False to perform actual group removals.
# When True, the script will only report what it would do.
DRY_RUN = True


def remove_user_group_memberships():
    """
    Finds all users in the target OU and removes all their group memberships.
    """
    if DRY_RUN:
        print("=" * 40)
        print("=== SCRIPT IS RUNNING IN DRY RUN MODE ===")
        print("=== No changes will be made.         ===")
        print("=" * 40 + "\n")

    print(f"Attempting to connect to target OU: {TARGET_OU_DN}")
    print("-" * 30)

    try:
        # Connect to the container object for the OU
        target_ou = adcontainer.ADContainer.from_dn(TARGET_OU_DN)
        print("Successfully connected to the OU.")
    except pyad_exceptions.InvalidDN as e:
        print(f"\n[ERROR] Invalid Distinguished Name: {e}")
        print("Please check that the OU path is spelled correctly and exists in AD.")
        return
    except Exception as e:
        print(f"\n[ERROR] Could not connect to the OU: {e}")
        print("Ensure you are running this on a domain-joined machine with correct permissions.")
        return

    # Get all user objects in the source OU
    try:
        users_in_ou = target_ou.get_members(recursive=False, filter_users=True)
    except Exception as e:
        print(f"\n[ERROR] Failed to retrieve users from the target OU: {e}")
        return

    users_list = list(users_in_ou)
    if not users_list:
        print("\nNo user objects found in the target OU. Nothing to do.")
        return

    print(f"\nFound {len(users_list)} user(s) to process.")

    # Iterate through each user
    for user in users_list:
        try:
            user_cn = user.get_attribute('cn', a_return_list=False)
            print(f"\nProcessing user: {user_cn}")

            # Get all groups the user is a member of
            member_of_groups = user.get_memberOf()

            if not member_of_groups:
                print("  - User is not a member of any groups.")
                continue

            for group in member_of_groups:
                group_name = group.get_attribute('cn', a_return_list=False)

                # CRITICAL: Do not remove users from the "Domain Users" group.
                if group_name.lower() == "domain users":
                    print(f"  - Skipping primary group: {group_name}")
                    continue

                print(f"  - Preparing to remove from group: {group_name}")

                if not DRY_RUN:
                    try:
                        # The remove_members method takes one or more AD objects
                        group.remove_members(user)
                        print("    ...REMOVED.")
                    except pyad_exceptions.win32_error as e:
                        print(f"    ...FAILED. Error: {e}")
                    except Exception as e:
                        print(f"    ...FAILED. An unexpected error occurred: {e}")
                else:
                    print("    ...SKIPPED (Dry Run).")

        except Exception as e:
            user_dn = user.distinguishedName
            print(f"  - FAILED to process user {user_dn}. An unexpected error occurred: {e}")

    print("-" * 30)
    print("\nScript complete.")
    if DRY_RUN:
        print("Dry Run finished. No changes were made.")
    else:
        print("Group membership removal process finished.")


if __name__ == "__main__":
    # It's good practice to clear pyad's cache in case AD has changed recently
    from pyad import pyad_utils
    pyad_utils.clear_cache()

    remove_user_group_memberships()
    input("\nPress Enter to exit...")
