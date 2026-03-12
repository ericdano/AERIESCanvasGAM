# PowerShell Script to Get All Users in an OU and its Sub-OUs

# This script requires the Active Directory module for Windows PowerShell.
# If you don't have it, you can install it using:
# Add-WindowsFeature RSAT-AD-PowerShell

# 1. Define the Distinguished Name of the OU you want to search.
#    You must replace "OU=MyDepartment,DC=example,DC=com" with the actual
#    Distinguished Name of your target OU.
#    Example: "OU=Users,OU=Company,DC=domain,DC=local"
$searchBaseOU = "OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us"

# 2. Use the Get-ADUser cmdlet to search for all user objects.
#    -SearchBase: Specifies the distinguished name of the container where the search starts.
#    -Filter:     The "*" character acts as a wildcard, retrieving all user objects.
#    -SearchScope: Specifies the scope of the search. 'Subtree' includes the base and all child OUs.
#    -Properties: Specifies which properties to retrieve. This example gets the default properties,
#                 plus 'SamAccountName' and 'Enabled'. You can add more as needed.
try {
    Write-Host "Searching for users in $searchBaseOU and its sub-OUs..."

    $users = Get-ADUser -server socrates -SearchBase $searchBaseOU `
                        -Filter * `
                        -SearchScope Subtree `
                        -Properties SamAccountName, Enabled, HomeDirectory

    # 3. Check if any users were found before processing.
    if ($users) {
        Write-Host "Found $($users.Count) user(s)."
        Write-Host "---------------------------------"
        
        # 4. Loop through the found users and display their key properties.
        foreach ($user in $users) {
            Write-Host "Fixing HomeDirect for ->Name: $($user.Name) sAMAccountName: $($user.SamAccountName) Enabled: $($user.Enabled) DistinguishedName: $($user.DistinguishedName) Home Directory: $($user.HomeDirectory)"
            # Set permissions for the new directory
            # This example grants full control to the user and removes inheritance
            if ($user.HomeDirectory) {
                $Acl = Get-Acl $user.HomeDirectory
                $Rule = New-Object System.Security.AccessControl.FileSystemAccessRule($user.SamAccountName, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
                $Acl.SetAccessRule($Rule)
                Set-Acl -Path $user.HomeDirectory -AclObject $Acl
                Write-Host "$($user.Name) home directory $($HomeDirectory) has permissions set."
            }
        }

        # 5. OPTIONAL: Export the results to a CSV file.
        #    Uncomment the line below to save the output.
        # $users | Select-Object Name, SamAccountName, Enabled, DistinguishedName | Export-Csv -Path "C:\temp\ADUsers.csv" -NoTypeInformation

        Write-Host "Script completed successfully."
    }
    else {
        Write-Host "No users found in the specified OU."
    }
}
catch {
    Write-Error "An error occurred: $_"
}
