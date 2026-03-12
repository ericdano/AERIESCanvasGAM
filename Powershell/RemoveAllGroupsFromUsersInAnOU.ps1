<#
.SYNOPSIS
    Removes all Active Directory group memberships for users in a specified Organizational Unit (OU).

.DESCRIPTION
    This script retrieves all user accounts from a specific OU and its sub-OUs.
    It then iterates through each user, finds all of their group memberships, and removes them from each group.

    IMPORTANT:
    By default, this script uses the -WhatIf parameter on the Remove-ADGroupMember cmdlet.
    This means it will only display the actions it WOULD take without actually performing them.
    To execute the changes, you must remove or comment out the "-WhatIf" parameter from the command on line 59.

    The script intentionally skips removing users from the "Domain Users" group, as this is typically the primary group
    and removing it can cause unforeseen issues with user accounts.

.PARAMETER OUPath
    The Distinguished Name (DN) of the Organizational Unit to target.
    You MUST update this variable to point to your target OU.

.EXAMPLE
    .\Remove-UserGroupMemberships.ps1
    (After setting the $OUPath variable inside the script)

.NOTES
    - Requires the Active Directory module for PowerShell.
    - Run this script with an account that has permissions to read users and remove group members in the target OU.
#>

# Import the Active Directory module
try {
    Import-Module ActiveDirectory -ErrorAction Stop
}
catch {
    Write-Warning "The Active Directory module could not be loaded. Please ensure the RSAT-AD-PowerShell feature is installed."
    # Pause the script to allow the user to read the message before the window closes.
    Read-Host -Prompt "Press Enter to exit"
    return
}

# --- PLEASE CONFIGURE THIS VARIABLE ---
# Specify the Distinguished Name (DN) of the Organizational Unit you want to target.
# Example: "OU=Marketing,OU=Users,DC=yourdomain,DC=com"
$OUPath = "OU=Students,OU=AHS,OU=Graduated 2025,DC=students,DC=acalanes,DC=k12,DC=ca,DC=us"

# --- SCRIPT LOGIC ---
Write-Host "Searching for users in OU: $OUPath" -ForegroundColor Yellow

# Get all users in the specified OU and any sub-OUs.
# A try-catch block handles cases where the OU doesn't exist or is misspelled.
try {
    $users = Get-ADUser -Server socrates -Filter * -SearchBase $OUPath -SearchScope Subtree -ErrorAction Stop
}
catch {
    Write-Error "Could not retrieve users. Please check the following:"
    Write-Error "- The OU path '$OUPath' is correct."
    Write-Error "- You have permissions to read users in this OU."
    Read-Host -Prompt "Press Enter to exit"
    return
}


if ($null -eq $users) {
    Write-Host "No users found in the specified OU. Exiting." -ForegroundColor Green
    Read-Host -Prompt "Press Enter to exit"
    return
}

Write-Host "Found $($users.Count) users. Processing group memberships..."

# Loop through each user found in the OU
foreach ($user in $users) {
    Write-Host "`nProcessing user: $($user.SamAccountName)" -ForegroundColor Cyan

    try {
        # Get all groups the user is a member of
        $groups = Get-ADPrincipalGroupMembership -Identity $user

        if ($null -eq $groups) {
            Write-Host "  - User is not a member of any groups."
            continue # Skip to the next user
        }

        # Loop through each group and remove the user
        foreach ($group in $groups) {
            # CRITICAL: Do not remove users from the "Domain Users" group.
            if ($group.Name -eq "Domain Users") {
                Write-Host "  - Skipping primary group: $($group.Name)" -ForegroundColor Gray
                continue # Skip to the next group
            }

            Write-Host "  - Preparing to remove from group: $($group.Name)"

            # --- SAFETY SWITCH ---
            # The -WhatIf parameter prevents the command from making actual changes.
            # It shows what would happen if the command ran.
            # To perform the removal, DELETE or COMMENT OUT the "-WhatIf" parameter below.
            Remove-ADGroupMember -Identity $group -Members $user -Confirm:$false -WhatIf
        }
    }
    catch {
        Write-Warning "An error occurred while processing user $($user.SamAccountName): $_"
    }
}

Write-Host "`nScript complete. Remember, -WhatIf mode was active." -ForegroundColor Green
Write-Host "No changes were made unless you removed the -WhatIf parameter." -ForegroundColor Yellow