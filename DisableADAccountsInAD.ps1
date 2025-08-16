# --------------------------------------------------------------------------------------------------
# Suspend Active Directory Accounts from a CSV
# --------------------------------------------------------------------------------------------------

# Import the Active Directory module
Import-Module ActiveDirectory

# Define the path to your CSV file
# IMPORTANT: Change this path to the location of your CSV file
$csvPath = $args[0]

# Define the distinguished name of the OU where suspended users will be moved
# IMPORTANT: Change this to the distinguished name of your 'Suspended Users' OU
$suspendedUsersOU = "OU=Disabled,OU=Students,DC=student,DC=acalanes,DC=k12,DC=ca,DC=us"

# Check if the CSV file exists
if (-not (Test-Path $csvPath)) {
    Write-Host "Error: CSV file not found at $csvPath." -ForegroundColor Red
    exit
}

# Check if the target OU exists
try {
    Get-ADOrganizationalUnit -server socrates -Identity $suspendedUsersOU -ErrorAction Stop | Out-Null
} catch {
    Write-Host "Error: The specified Suspended Users OU was not found. Please check the path: $suspendedUsersOU" -ForegroundColor Red
    exit
}

# Import the CSV file and loop through each user
$users = Import-Csv -Path $csvPath

if ($null -eq $users -or $users.Count -eq 0) {
    Write-Host "The CSV file is empty or formatted incorrectly." -ForegroundColor Yellow
    exit
}

foreach ($user in $users) {
    $samAccountName = $user.STUID

    # Find the Active Directory user object
    $adUser = Get-ADUser -server socrates -Identity $samAccountName -ErrorAction SilentlyContinue

    if ($adUser) {
        try {
            # Disable the user account
            Disable-ADAccount -Identity $adUser -PassThru | Out-Null
            
            # Set a description for the account
            $description = "Account suspended on $(Get-Date -Format 'yyyy-MM-dd')"
            Set-ADUser -Server socrates -Identity $adUser -Description $description
            
            # Move the user to the designated 'Suspended Users' OU
            Move-ADObject -Server socrates -Identity $adUser -TargetPath $suspendedUsersOU
            
            Write-Host "Successfully suspended account: $samAccountName" -ForegroundColor Green
        }
        catch {
            Write-Host "Failed to suspend account: $samAccountName. Error: $($_.Exception.Message)" -ForegroundColor Red
        }
    } else {
        Write-Host "User not found in Active Directory: $samAccountName" -ForegroundColor Yellow
    }
}