-- Create table [user]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[user]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [user] (
      [id] int PRIMARY KEY IDENTITY(1,1),
      [email] nvarchar(255),
      [password_hash] nvarchar(255),
      [role] nvarchar(50),
      [created_at] datetime2,
      [updated_at] datetime2,
      CONSTRAINT chk_user_role CHECK ([role] IN ('client','account_manager'))
    );
END
GO

-- Create table [account_manager]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[account_manager]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [account_manager] (
      [account_manager_id] int PRIMARY KEY,
      [username] nvarchar(255),
      [password] nvarchar(255),
      [first_name] nvarchar(255),
      [last_name] nvarchar(255),
      [email] nvarchar(255),
      [phone] nvarchar(255),
      [admin] BIT,
      [active] BIT,
      [created_at] datetime2,
      [updated_at] datetime2
    );
END
GO

-- Create table [client]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[client]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [client] (
      [client_id] int PRIMARY KEY IDENTITY(1,1),
      [account_manager_id] int,
      [name] nvarchar(255),
      [logo_url] nvarchar(255),
      [tax_id] nvarchar(255),
      [address] nvarchar(255),
      [email] nvarchar(255),
      [phone] nvarchar(255),
      [webpage] nvarchar(255),
      [sector] nvarchar(255),
      [billing] nvarchar(255),         
      [language] nvarchar(255),        
      [status] nvarchar(255),          
      [notes] nvarchar(max),           
      [active] BIT,
      [created_at] datetime2,
      [updated_at] datetime2
    );
END
GO

-- Create table [client_contact]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[client_contact]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [client_contact] (
      [client_contact_id] int PRIMARY KEY,
      [client_id] int,
      [first_name] nvarchar(255),
      [last_name] nvarchar(255),
      [profile_pic_url] nvarchar(255),
      [role] nvarchar(255),
      [type] nvarchar(255),       
      [email] nvarchar(255),
      [phone] nvarchar(255),
      [created_at] datetime2,
      [updated_at] datetime2
    );
END
GO

-- Create table [client_tender]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[client_tender]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [client_tender] (
      [client_tender_id] int PRIMARY KEY IDENTITY(1,1),
      [client_id] int,
      [tender_id] int,
      [current_internal_situation] nvarchar(255),
      [assigned_at] datetime2,
      [deadline_internal] datetime2,
      [internal_notes] nvarchar(max),
      [active] BIT,
      [created_at] datetime2,
      [updated_at] datetime2
    );
END
GO

-- Create table [task]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[task]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [task] (
      [task_id] int PRIMARY KEY IDENTITY(1,1),
      [client_tender_id] int,
      [title] nvarchar(255),         
      [deadline] datetime2
    );
END
GO

-- Create table [comment]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[comment]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [comment] (
      [comment_id] int PRIMARY KEY IDENTITY(1,1),
      [task_id] int,                 
      [comment_text] nvarchar(max)   
    );
END
GO

-- Create table [rejection_reason]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[rejection_reason]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [rejection_reason] (
      [rejection_reason_id] int PRIMARY KEY,  
      [title] nvarchar(255),                  
      [comments] nvarchar(max)                
    );
END
GO

-- Create table [client_tender_situation_history]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[client_tender_situation_history]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [client_tender_situation_history] (
      [client_tender_situation_history_id] int PRIMARY KEY IDENTITY(1,1),
      [client_tender_id] int,
      [old_situation] nvarchar(255),
      [new_situation] nvarchar(255),
      [change_date] datetime2,
      [comments] nvarchar(max),
      [created_at] datetime2,
      [updated_at] datetime2
    );
END
GO

-- Create table [client_tender_template]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[client_tender_template]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [client_tender_template] (
      [client_tender_template_id] int PRIMARY KEY IDENTITY(1,1),
      [client_tender_id] int,
      [template_id] int,
      [date_used] datetime2,
      [comments] nvarchar(max),
      [created_at] datetime2,
      [updated_at] datetime2
    );
END
GO

-- Create table [template]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[template]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [template] (
      [template_id] int PRIMARY KEY IDENTITY(1,1),
      [client_id] int,
      [template_name] nvarchar(255),
      [template_usage] nvarchar(255),
      [template_url] nvarchar(255),
      [version] nvarchar(255),
      [active] BIT,
      [created_at] datetime2,
      [updated_at] datetime2
    );
END
GO

-- Create table [cpv]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[cpv]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [cpv] (
      [code] nvarchar(255) PRIMARY KEY,
      [description] nvarchar(max),
      [parent_code] nvarchar(255),
      [path] nvarchar(255),
      [active] BIT,
      [created_at] datetime2,
      [updated_at] datetime2
    );
END
GO

-- Create table [client_cpv]
IF NOT EXISTS (SELECT * FROM sys.objects 
               WHERE object_id = OBJECT_ID(N'[dbo].[client_cpv]') 
                 AND type = N'U')
BEGIN
    CREATE TABLE [client_cpv] (
      [client_id] int,
      [cpv_code] nvarchar(255),
      [created_at] datetime2,
      [updated_at] datetime2,
      PRIMARY KEY ([client_id], [cpv_code])
    );
END
GO

-- Add FK: account_manager -> user
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_account_manager_user')
BEGIN
    ALTER TABLE [account_manager]
      ADD CONSTRAINT fk_account_manager_user FOREIGN KEY ([account_manager_id]) REFERENCES [user] ([id]);
END
GO

-- Add FK: client -> account_manager
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_client_account_manager')
BEGIN
    ALTER TABLE [client]
      ADD CONSTRAINT fk_client_account_manager FOREIGN KEY ([account_manager_id]) REFERENCES [account_manager] ([account_manager_id]);
END
GO

-- Add FK: client_contact -> user
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_client_contact_user')
BEGIN
    ALTER TABLE [client_contact]
      ADD CONSTRAINT fk_client_contact_user FOREIGN KEY ([client_contact_id]) REFERENCES [user] ([id]);
END
GO

-- Add FK: client_tender -> client
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_client_tender_client')
BEGIN
    ALTER TABLE [client_tender]
      ADD CONSTRAINT fk_client_tender_client FOREIGN KEY ([client_id]) REFERENCES [client] ([client_id]);
END
GO

-- Add FK: task -> client_tender
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_task_client_tender')
BEGIN
    ALTER TABLE [task]
      ADD CONSTRAINT fk_task_client_tender FOREIGN KEY ([client_tender_id]) REFERENCES [client_tender] ([client_tender_id]);
END
GO

-- Add FK: comment -> task
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_comment_task')
BEGIN
    ALTER TABLE [comment]
      ADD CONSTRAINT fk_comment_task FOREIGN KEY ([task_id]) REFERENCES [task] ([task_id]);
END
GO

-- Add FK: rejection_reason -> client_tender
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_rejection_reason_client_tender')
BEGIN
    ALTER TABLE [rejection_reason]
      ADD CONSTRAINT fk_rejection_reason_client_tender FOREIGN KEY ([rejection_reason_id]) REFERENCES [client_tender] ([client_tender_id]);
END
GO

-- Add FK: client_tender_situation_history -> client_tender
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_client_tender_situation_history_client_tender')
BEGIN
    ALTER TABLE [client_tender_situation_history]
      ADD CONSTRAINT fk_client_tender_situation_history_client_tender FOREIGN KEY ([client_tender_id]) REFERENCES [client_tender] ([client_tender_id]);
END
GO

-- Add FK: client_tender_template -> client_tender
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_client_tender_template_client_tender')
BEGIN
    ALTER TABLE [client_tender_template]
      ADD CONSTRAINT fk_client_tender_template_client_tender FOREIGN KEY ([client_tender_id]) REFERENCES [client_tender] ([client_tender_id]);
END
GO

-- Add FK: client_tender_template -> template
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_client_tender_template_template')
BEGIN
    ALTER TABLE [client_tender_template]
      ADD CONSTRAINT fk_client_tender_template_template FOREIGN KEY ([template_id]) REFERENCES [template] ([template_id]);
END
GO

-- Add FK: template -> client
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_template_client')
BEGIN
    ALTER TABLE [template]
      ADD CONSTRAINT fk_template_client FOREIGN KEY ([client_id]) REFERENCES [client] ([client_id]);
END
GO

-- Add FK: cpv parent (self-referencing)
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_cpv_parent')
BEGIN
    ALTER TABLE [cpv]
      ADD CONSTRAINT fk_cpv_parent FOREIGN KEY ([parent_code]) REFERENCES [cpv] ([code]);
END
GO

-- Add FK: client_cpv -> client
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_client_cpv_client')
BEGIN
    ALTER TABLE [client_cpv]
      ADD CONSTRAINT fk_client_cpv_client FOREIGN KEY ([client_id]) REFERENCES [client] ([client_id]);
END
GO

-- Add FK: client_cpv -> cpv
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'fk_client_cpv_cpv')
BEGIN
    ALTER TABLE [client_cpv]
      ADD CONSTRAINT fk_client_cpv_cpv FOREIGN KEY ([cpv_code]) REFERENCES [cpv] ([code]);
END
GO
