import ClientData
import ClientFiles
import collections
import dircache
import hashlib
import httplib
import itertools
import HydrusConstants as HC
import ClientDownloading
import HydrusEncryption
import HydrusExceptions
import HydrusFileHandling
import HydrusImageHandling
import HydrusNATPunch
import HydrusServer
import HydrusSerialisable
import HydrusTagArchive
import HydrusTags
import HydrusThreading
import ClientConstants as CC
import os
import Queue
import random
import shutil
import sqlite3
import stat
import sys
import threading
import time
import traceback
import wx
import yaml
import HydrusData
import HydrusNetworking
import HydrusGlobals

def DAEMONCheckExportFolders():
    
    options = wx.GetApp().GetOptions()
    
    if not options[ 'pause_export_folders_sync' ]:
        
        export_folders = wx.GetApp().Read( 'export_folders' )
        
        for export_folder in export_folders:
            
            export_folder.DoWork()
            
        
    
def DAEMONCheckImportFolders():
    
    options = wx.GetApp().GetOptions()
    
    if not options[ 'pause_import_folders_sync' ]:
        
        import_folders = wx.GetApp().Read( 'import_folders' )
        
        for ( folder_path, details ) in import_folders.items():
            
            if HydrusData.TimeHasPassed( details[ 'last_checked' ] + details[ 'check_period' ] ):
                
                if os.path.exists( folder_path ) and os.path.isdir( folder_path ):
                    
                    filenames = dircache.listdir( folder_path )
                    
                    raw_paths = [ folder_path + os.path.sep + filename for filename in filenames ]
                    
                    all_paths = ClientFiles.GetAllPaths( raw_paths )
                    
                    if details[ 'type' ] == HC.IMPORT_FOLDER_TYPE_SYNCHRONISE: 
                        
                        all_paths = [ path for path in all_paths if path not in details[ 'cached_imported_paths' ] ]
                        
                    
                    all_paths = [ path for path in all_paths if path not in details[ 'failed_imported_paths' ] ]
                    
                    successful_hashes = set()
                    
                    for ( i, path ) in enumerate( all_paths ):
                        
                        if options[ 'pause_import_folders_sync' ]: return
                        
                        info = os.lstat( path )
                        
                        size = info[6]
                        
                        if size == 0: continue
                        
                        ( os_file_handle, temp_path ) = HydrusFileHandling.GetTempPath()
                        
                        try:
                            
                            try:
                                
                                # try to get a write lock just to check it isn't being written to right now
                                
                                with open( path, 'ab' ) as f:
                                    
                                    pass
                                    
                                
                                with open( path, 'rb' ) as f_source:
                                    
                                    with open( temp_path, 'wb' ) as f_dest:
                                        
                                        HydrusFileHandling.CopyFileLikeToFileLike( f_source, f_dest )
                                        
                                    
                                
                            except:
                                
                                # could not lock, so try again later
                                
                                continue
                                
                            
                            try:
                                
                                if details[ 'local_tag' ] is not None: service_keys_to_tags = { CC.LOCAL_TAG_SERVICE_KEY : { details[ 'local_tag' ] } }
                                else: service_keys_to_tags = {}
                                
                                ( result, hash ) = wx.GetApp().WriteSynchronous( 'import_file', temp_path, service_keys_to_tags = service_keys_to_tags )
                                
                                if result in ( CC.STATUS_SUCCESSFUL, CC.STATUS_REDUNDANT ):
                                    
                                    successful_hashes.add( hash )
                                    
                                    if details[ 'type' ] == HC.IMPORT_FOLDER_TYPE_SYNCHRONISE: details[ 'cached_imported_paths' ].add( path )
                                    
                                elif result == CC.STATUS_DELETED:
                                    
                                    details[ 'failed_imported_paths' ].add( path )
                                    
                                
                                if details[ 'type' ] == HC.IMPORT_FOLDER_TYPE_DELETE:
                                    
                                    try: os.remove( path )
                                    except: details[ 'failed_imported_paths' ].add( path )
                                    
                                
                            except:
                                
                                details[ 'failed_imported_paths' ].add( path )
                                
                                HydrusData.ShowText( 'Import folder failed to import ' + path + ':' + os.linesep * 2 + traceback.format_exc() )
                                
                            
                        finally:
                            
                            HydrusFileHandling.CleanUpTempPath( os_file_handle, temp_path )
                            
                        
                    
                    if len( successful_hashes ) > 0:
                        
                        text = HydrusData.ToString( len( successful_hashes ) ) + ' files imported from ' + folder_path
                        
                        job_key = HydrusData.JobKey()
                        
                        job_key.SetVariable( 'popup_title', 'import folder' )
                        job_key.SetVariable( 'popup_text_1', text )
                        job_key.SetVariable( 'popup_files', successful_hashes )
                        
                        HydrusGlobals.pubsub.pub( 'message', job_key )
                        
                    
                    details[ 'last_checked' ] = HydrusData.GetNow()
                    
                    wx.GetApp().WriteSynchronous( 'import_folder', folder_path, details )
                    
                
            
        
    
def DAEMONDownloadFiles():
    
    hashes = wx.GetApp().Read( 'downloads' )
    
    num_downloads = len( hashes )
    
    if num_downloads > 0:
        
        successful_hashes = set()
        
        job_key = HydrusData.JobKey()
        
        job_key.SetVariable( 'popup_text_1', 'initialising downloader' )
        
        HydrusGlobals.pubsub.pub( 'message', job_key )
        
        for hash in hashes:
            
            job_key.SetVariable( 'popup_text_1', 'downloading ' + HydrusData.ConvertIntToPrettyString( num_downloads - len( successful_hashes ) ) + ' files from repositories' )
            
            ( media_result, ) = wx.GetApp().Read( 'media_results', CC.COMBINED_FILE_SERVICE_KEY, ( hash, ) )
            
            service_keys = list( media_result.GetLocationsManager().GetCurrent() )
            
            random.shuffle( service_keys )
            
            for service_key in service_keys:
                
                if service_key == CC.LOCAL_FILE_SERVICE_KEY: break
                elif service_key == CC.TRASH_SERVICE_KEY: continue
                
                try: file_repository = wx.GetApp().GetServicesManager().GetService( service_key )
                except HydrusExceptions.NotFoundException: continue
                
                if file_repository.CanDownload(): 
                    
                    try:
                        
                        request_args = { 'hash' : hash.encode( 'hex' ) }
                        
                        ( os_file_handle, temp_path ) = HydrusFileHandling.GetTempPath()
                        
                        try:
                            
                            file_repository.Request( HC.GET, 'file', request_args = request_args, temp_path = temp_path )
                            
                            wx.GetApp().WaitUntilWXThreadIdle()
                            
                            wx.GetApp().WriteSynchronous( 'import_file', temp_path, override_deleted = True )
                            
                            successful_hashes.add( hash )
                            
                            break
                            
                        finally:
                            
                            HydrusFileHandling.CleanUpTempPath( os_file_handle, temp_path )
                            
                        
                    except HydrusExceptions.ServerBusyException:
                        
                        job_key.SetVariable( 'popup_text_1', file_repository.GetName() + ' was busy. waiting 30s before trying again' )
                        
                        time.sleep( 30 )
                        
                        job_key.Delete()
                        
                        HydrusGlobals.pubsub.pub( 'notify_new_downloads' )
                        
                        return
                        
                    except Exception as e:
                        
                        HydrusData.ShowText( 'Error downloading file!' )
                        HydrusData.ShowException( e )
                        
                    
                
                if HydrusGlobals.shutdown: return
                
            
        
        if len( successful_hashes ) > 0:
            
            job_key.SetVariable( 'popup_text_1', HydrusData.ConvertIntToPrettyString( len( successful_hashes ) ) + ' files downloaded' )
            
        else:
            
            job_key.SetVariable( 'popup_text_1', 'all files failed to download' )
            
        
        job_key.Delete()
        
    
def DAEMONFlushServiceUpdates( list_of_service_keys_to_service_updates ):
    
    service_keys_to_service_updates = HydrusData.MergeKeyToListDicts( list_of_service_keys_to_service_updates )
    
    wx.GetApp().WriteSynchronous( 'service_updates', service_keys_to_service_updates )
    
def DAEMONMaintainTrash():
    
    max_size = HC.options[ 'trash_max_size' ] * 1048576
    max_age = HC.options[ 'trash_max_age' ] * 3600
    
    if max_size is not None:
        
        service_info = wx.GetApp().Read( 'service_info', CC.TRASH_SERVICE_KEY )
        
        while service_info[ HC.SERVICE_INFO_TOTAL_SIZE ] > max_size:
            
            if HydrusGlobals.shutdown:
                
                return
                
            
            hashes = wx.GetApp().Read( 'oldest_trash_hashes' )
            
            if len( hashes ) == 0:
                
                return
                
            
            content_update = HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_FILES, HC.CONTENT_UPDATE_DELETE, hashes )
            
            service_keys_to_content_updates = { CC.TRASH_SERVICE_KEY : [ content_update ] }
            
            wx.GetApp().WaitUntilWXThreadIdle()
            
            wx.GetApp().WriteSynchronous( 'content_updates', service_keys_to_content_updates )
            
            service_info = wx.GetApp().Read( 'service_info', CC.TRASH_SERVICE_KEY )
            
        
    
    if max_age is not None:
        
        hashes = wx.GetApp().Read( 'oldest_trash_hashes', minimum_age = max_age )
        
        while len( hashes ) > 0:
            
            if HydrusGlobals.shutdown:
                
                return
                
            
            content_update = HydrusData.ContentUpdate( HC.CONTENT_DATA_TYPE_FILES, HC.CONTENT_UPDATE_DELETE, hashes )
            
            service_keys_to_content_updates = { CC.TRASH_SERVICE_KEY : [ content_update ] }
            
            wx.GetApp().WaitUntilWXThreadIdle()
            
            wx.GetApp().WriteSynchronous( 'content_updates', service_keys_to_content_updates )
            
            hashes = wx.GetApp().Read( 'oldest_trash_hashes', minimum_age = max_age )
            
        
    
def DAEMONResizeThumbnails():
    
    if not wx.GetApp().CurrentlyIdle(): return
    
    full_size_thumbnail_paths = { path for path in ClientFiles.IterateAllThumbnailPaths() if not path.endswith( '_resized' ) }
    
    resized_thumbnail_paths = { path[:-8] for path in ClientFiles.IterateAllThumbnailPaths() if path.endswith( '_resized' ) }
    
    thumbnail_paths_to_render = list( full_size_thumbnail_paths.difference( resized_thumbnail_paths ) )
    
    random.shuffle( thumbnail_paths_to_render )
    
    i = 0
    
    limit = max( 100, len( thumbnail_paths_to_render ) / 10 )
    
    options = wx.GetApp().GetOptions()
    
    for thumbnail_path in thumbnail_paths_to_render:
        
        try:
            
            thumbnail_resized = HydrusFileHandling.GenerateThumbnail( thumbnail_path, options[ 'thumbnail_dimensions' ] )
            
            thumbnail_resized_path = thumbnail_path + '_resized'
            
            with open( thumbnail_resized_path, 'wb' ) as f: f.write( thumbnail_resized )
            
        except IOError as e: HydrusData.ShowText( 'Thumbnail read error:' + os.linesep + traceback.format_exc() )
        except Exception as e: HydrusData.ShowText( 'Thumbnail rendering error:' + os.linesep + traceback.format_exc() )
        
        if i % 10 == 0: time.sleep( 2 )
        else:
            
            if limit > 10000: time.sleep( 0.05 )
            elif limit > 1000: time.sleep( 0.25 )
            else: time.sleep( 0.5 )
            
        
        i += 1
        
        if i > limit: break
        
        if HydrusGlobals.shutdown: break
        
    
def DAEMONSynchroniseAccounts():
    
    services = wx.GetApp().GetServicesManager().GetServices( HC.RESTRICTED_SERVICES )
    
    options = wx.GetApp().GetOptions()
    
    do_notify = False
    
    for service in services:
        
        service_key = service.GetServiceKey()
        service_type = service.GetServiceType()
        
        account = service.GetInfo( 'account' )
        credentials = service.GetCredentials()
        
        if service_type in HC.REPOSITORIES:
            
            if options[ 'pause_repo_sync' ]: continue
            
            info = service.GetInfo()
            
            if info[ 'paused' ]: continue
            
        
        if account.IsStale() and credentials.HasAccessKey() and not service.HasRecentError():
            
            try:
                
                response = service.Request( HC.GET, 'account' )
                
                account = response[ 'account' ]
                
                account.MakeFresh()
                
                wx.GetApp().WriteSynchronous( 'service_updates', { service_key : [ HydrusData.ServiceUpdate( HC.SERVICE_UPDATE_ACCOUNT, account ) ] } )
                
                do_notify = True
                
            except Exception as e:
                
                print( 'Failed to refresh account for ' + service.GetName() + ':' )
                
                print( traceback.format_exc() )
                
            
        
    
    if do_notify: HydrusGlobals.pubsub.pub( 'notify_new_permissions' )
    
def DAEMONSynchroniseRepositories():
    
    HydrusGlobals.repos_changed = False
    
    options = wx.GetApp().GetOptions()
    
    if not options[ 'pause_repo_sync' ]:
        
        services = wx.GetApp().GetServicesManager().GetServices( HC.REPOSITORIES )
        
        HydrusGlobals.currently_processing_updates = True
        
        for service in services:
            
            service.Sync()
            
        
        HydrusGlobals.currently_processing_updates = False
        
        time.sleep( 5 )
        
    
def DAEMONSynchroniseSubscriptions():
    
    HydrusGlobals.subs_changed = False
    
    options = wx.GetApp().GetOptions()
    
    if not options[ 'pause_subs_sync' ]:
        
        subscription_names = wx.GetApp().Read( 'subscription_names' )
        
        for name in subscription_names:
            
            info = wx.GetApp().Read( 'subscription', name )
            
            site_type = info[ 'site_type' ]
            query_type = info[ 'query_type' ]
            query = info[ 'query' ]
            frequency_type = info[ 'frequency_type' ]
            frequency = info[ 'frequency' ]
            get_tags_if_redundant = info[ 'get_tags_if_redundant' ]
            initial_limit = info[ 'initial_limit' ]
            advanced_tag_options = info[ 'advanced_tag_options' ]
            import_file_options = info[ 'advanced_import_options' ]
            last_checked = info[ 'last_checked' ]
            url_cache = info[ 'url_cache' ]
            paused = info[ 'paused' ]
            
            if paused: continue
            
            now = HydrusData.GetNow()
            
            if last_checked is None: last_checked = 0
            
            if last_checked + ( frequency_type * frequency ) < now:
                
                try:
                    
                    job_key = HydrusData.JobKey( pausable = True, cancellable = True )
                    
                    job_key.SetVariable( 'popup_title', 'subscriptions - ' + name )
                    job_key.SetVariable( 'popup_text_1', 'checking' )
                    
                    HydrusGlobals.pubsub.pub( 'message', job_key )
                    
                    do_tags = len( advanced_tag_options ) > 0
                    
                    if site_type == HC.SITE_TYPE_BOORU:
                        
                        ( booru_name, booru_query_type ) = query_type
                        
                        try: booru = wx.GetApp().Read( 'remote_booru', booru_name )
                        except: raise Exception( 'While attempting to execute a subscription on booru ' + name + ', the client could not find that booru in the db.' )
                        
                        tags = query.split( ' ' )
                        
                        all_args = ( ( booru_name, tags ), )
                        
                    elif site_type == HC.SITE_TYPE_HENTAI_FOUNDRY:
                        
                        info = {}
                        
                        info[ 'rating_nudity' ] = 3
                        info[ 'rating_violence' ] = 3
                        info[ 'rating_profanity' ] = 3
                        info[ 'rating_racism' ] = 3
                        info[ 'rating_sex' ] = 3
                        info[ 'rating_spoilers' ] = 3
                        
                        info[ 'rating_yaoi' ] = 1
                        info[ 'rating_yuri' ] = 1
                        info[ 'rating_teen' ] = 1
                        info[ 'rating_guro' ] = 1
                        info[ 'rating_furry' ] = 1
                        info[ 'rating_beast' ] = 1
                        info[ 'rating_male' ] = 1
                        info[ 'rating_female' ] = 1
                        info[ 'rating_futa' ] = 1
                        info[ 'rating_other' ] = 1
                        
                        info[ 'filter_media' ] = 'A'
                        info[ 'filter_order' ] = 'date_new'
                        info[ 'filter_type' ] = 0
                        
                        advanced_hentai_foundry_options = info
                        
                        if query_type == 'artist': all_args = ( ( 'artist pictures', query, advanced_hentai_foundry_options ), ( 'artist scraps', query, advanced_hentai_foundry_options ) )
                        else:
                            
                            tags = query.split( ' ' )
                            
                            all_args = ( ( query_type, tags, advanced_hentai_foundry_options ), )
                            
                        
                    elif site_type == HC.SITE_TYPE_PIXIV: all_args = ( ( query_type, query ), )
                    else: all_args = ( ( query, ), )
                    
                    gallery_parsers = [ ClientDownloading.GetGalleryParser( site_type, *args ) for args in all_args ]
                    
                    gallery_parsers[0].SetupGallerySearch() # for now this is cookie-based for hf, so only have to do it on one
                    
                    all_urls = []
                    
                    page_index = 0
                    
                    while True:
                        
                        while options[ 'pause_subs_sync' ]:
                            
                            ( i_paused, should_quit ) = job_key.WaitIfNeeded()
                            
                            if should_quit:
                                
                                break
                                
                            
                            time.sleep( 0.1 )
                            
                            job_key.SetVariable( 'popup_text_1', 'subscriptions paused' )
                            
                            if HydrusGlobals.subs_changed:
                                
                                job_key.SetVariable( 'popup_text_1', 'subscriptions were changed during processing; this job was abandoned' )
                                
                                print( job_key.ToString() )
                                
                                job_key.Cancel()
                                
                                time.sleep( 5 )
                                
                                job_key.Delete()
                                
                                HydrusGlobals.pubsub.pub( 'notify_restart_subs_sync_daemon' )
                                
                                return
                                
                            
                        
                        ( i_paused, should_quit ) = job_key.WaitIfNeeded()
                        
                        if should_quit:
                            
                            break
                            
                        
                        if last_checked == 0 and initial_limit is not None and len( all_urls ) >= initial_limit: break
                        
                        gallery_parsers_to_remove = []
                        
                        for gallery_parser in gallery_parsers:
                            
                            if last_checked == 0 and initial_limit is not None and len( all_urls ) >= initial_limit: break
                            
                            page_of_urls = gallery_parser.GetPage( page_index )
                            
                            if len( page_of_urls ) == 0: gallery_parsers_to_remove.append( gallery_parser )
                            else:
                                
                                fresh_urls = [ url for url in page_of_urls if url not in url_cache ]
                                
                                reached_url_cache = len( fresh_urls ) != len( page_of_urls )
                                
                                if reached_url_cache: gallery_parsers_to_remove.append( gallery_parser )
                                
                                if initial_limit is not None:
                                    
                                    while len( fresh_urls ) > 0:
                                        
                                        url = fresh_urls.pop( 0 )
                                        
                                        all_urls.append( url )
                                        
                                        if len( all_urls ) >= initial_limit:
                                            
                                            break
                                            
                                        
                                    
                                else:
                                    
                                    all_urls.extend( fresh_urls )
                                    
                                
                                job_key.SetVariable( 'popup_text_1', 'found ' + HydrusData.ConvertIntToPrettyString( len( all_urls ) ) + ' new files' )
                                
                            
                            time.sleep( 5 )
                            
                        
                        for gallery_parser in gallery_parsers_to_remove: gallery_parsers.remove( gallery_parser )
                        
                        if len( gallery_parsers ) == 0: break
                        
                        page_index += 1
                        
                    
                    all_urls.reverse() # to do oldest first, which means we can save incrementally
                    
                    num_new = 0
                    
                    successful_hashes = set()
                    
                    for ( i, url ) in enumerate( all_urls ):
                        
                        while options[ 'pause_subs_sync' ]:
                            
                            ( i_paused, should_quit ) = job_key.WaitIfNeeded()
                            
                            if should_quit:
                                
                                break
                                
                            
                            time.sleep( 0.1 )
                            
                            job_key.SetVariable( 'popup_text_1', 'subscriptions paused' )
                            
                            if HydrusGlobals.subs_changed:
                                
                                job_key.SetVariable( 'popup_text_1', 'subscriptions were changed during processing; this job was abandoned' )
                                
                                print( job_key.ToString() )
                                
                                job_key.Cancel()
                                
                                time.sleep( 5 )
                                
                                job_key.Delete()
                                
                                HydrusGlobals.pubsub.pub( 'notify_restart_subs_sync_daemon' )
                                
                                return
                                
                            
                        
                        ( i_paused, should_quit ) = job_key.WaitIfNeeded()
                        
                        if should_quit:
                            
                            break
                            
                        
                        try:
                            
                            url_cache.add( url )
                            
                            x_out_of_y = 'file ' + HydrusData.ConvertValueRangeToPrettyString( i, len( all_urls ) ) + ': '
                            
                            job_key.SetVariable( 'popup_text_1', x_out_of_y + 'checking url status' )
                            job_key.SetVariable( 'popup_gauge_1', ( i, len( all_urls ) ) )
                            
                            if len( successful_hashes ) > 0:
                                
                                job_key_s_h = set( successful_hashes )
                                
                                job_key.SetVariable( 'popup_files', job_key_s_h )
                                
                            
                            ( status, hash ) = wx.GetApp().Read( 'url_status', url )
                            
                            if status == CC.STATUS_DELETED and not import_file_options[ 'exclude_deleted_files' ]: status = CC.STATUS_NEW
                            
                            if status == CC.STATUS_REDUNDANT:
                                
                                if do_tags and get_tags_if_redundant:
                                    
                                    try:
                                        
                                        job_key.SetVariable( 'popup_text_1', x_out_of_y + 'found file in db, fetching tags' )
                                        
                                        tags = gallery_parser.GetTags( url )
                                        
                                        service_keys_to_tags = ClientDownloading.ConvertTagsToServiceKeysToTags( tags, advanced_tag_options )
                                        
                                        service_keys_to_content_updates = ClientDownloading.ConvertServiceKeysToTagsToServiceKeysToContentUpdates( hash, service_keys_to_tags )
                                        
                                        wx.GetApp().WriteSynchronous( 'content_updates', service_keys_to_content_updates )
                                        
                                    except: pass
                                    
                                
                            elif status == CC.STATUS_NEW:
                                
                                num_new += 1
                                
                                job_key.SetVariable( 'popup_text_1', x_out_of_y + 'downloading file' )
                                
                                ( os_file_handle, temp_path ) = HydrusFileHandling.GetTempPath()
                                
                                try:
                                    
                                    if do_tags: tags = gallery_parser.GetFileAndTags( temp_path, url )
                                    else:
                                        
                                        gallery_parser.GetFile( temp_path, url )
                                        
                                        tags = []
                                        
                                    
                                    service_keys_to_tags = ClientDownloading.ConvertTagsToServiceKeysToTags( tags, advanced_tag_options )
                                    
                                    job_key.SetVariable( 'popup_text_1', x_out_of_y + 'importing file' )
                                    
                                    ( status, hash ) = wx.GetApp().WriteSynchronous( 'import_file', temp_path, import_file_options = import_file_options, service_keys_to_tags = service_keys_to_tags, url = url )
                                    
                                finally:
                                    
                                    HydrusFileHandling.CleanUpTempPath( os_file_handle, temp_path )
                                    
                                
                                if status in ( CC.STATUS_SUCCESSFUL, CC.STATUS_REDUNDANT ): successful_hashes.add( hash )
                                
                            
                        except Exception as e:
                            
                            HydrusData.ShowText( 'While trying to execute subscription ' + name + ', the url ' + url + ' caused this problem:' )
                            
                            HydrusData.ShowException( e )
                            
                        
                        if i % 20 == 0:
                            
                            info[ 'site_type' ] = site_type
                            info[ 'query_type' ] = query_type
                            info[ 'query' ] = query
                            info[ 'frequency_type' ] = frequency_type
                            info[ 'frequency' ] = frequency
                            info[ 'get_tags_if_redundant' ] = get_tags_if_redundant
                            info[ 'initial_limit' ] = initial_limit
                            info[ 'advanced_tag_options' ] = advanced_tag_options
                            info[ 'advanced_import_options' ] = import_file_options
                            info[ 'last_checked' ] = last_checked
                            info[ 'url_cache' ] = url_cache
                            info[ 'paused' ] = paused
                            
                            wx.GetApp().WriteSynchronous( 'subscription', name, info )
                            
                        
                        wx.GetApp().WaitUntilWXThreadIdle()
                        
                        time.sleep( 3 )
                        
                    
                    job_key.DeleteVariable( 'popup_gauge_1' )
                    
                    if len( successful_hashes ) > 0:
                        
                        job_key.SetVariable( 'popup_text_1', HydrusData.ToString( len( successful_hashes ) ) + ' files imported' )
                        job_key.SetVariable( 'popup_files', successful_hashes )
                        
                    else: job_key.SetVariable( 'popup_text_1', 'no new files' )
                    
                    print( job_key.ToString() )
                    
                    job_key.DeleteVariable( 'popup_text_1' )
                    
                    if len( successful_hashes ) > 0: job_key.Finish()
                    else: job_key.Delete()
                    
                    last_checked = now
                    
                except Exception as e:
                    
                    job_key.Cancel()
                    
                    last_checked = now + HC.UPDATE_DURATION
                    
                    HydrusData.ShowText( 'Problem with ' + name + ':' )
                    
                    HydrusData.ShowException( e )
                    
                    time.sleep( 3 )
                    
                
                info[ 'site_type' ] = site_type
                info[ 'query_type' ] = query_type
                info[ 'query' ] = query
                info[ 'frequency_type' ] = frequency_type
                info[ 'frequency' ] = frequency
                info[ 'get_tags_if_redundant' ] = get_tags_if_redundant
                info[ 'initial_limit' ] = initial_limit
                info[ 'advanced_tag_options' ] = advanced_tag_options
                info[ 'advanced_import_options' ] = import_file_options
                info[ 'last_checked' ] = last_checked
                info[ 'url_cache' ] = url_cache
                info[ 'paused' ] = paused
                
                wx.GetApp().WriteSynchronous( 'subscription', name, info )
                
            
        
        time.sleep( 3 )
        
    
def DAEMONUPnP():
    
    try:
        
        local_ip = HydrusNATPunch.GetLocalIP()
        
        current_mappings = HydrusNATPunch.GetUPnPMappings()
        
        our_mappings = { ( internal_client, internal_port ) : external_port for ( description, internal_client, internal_port, external_ip_address, external_port, protocol, enabled ) in current_mappings }
        
    except: return # This IGD probably doesn't support UPnP, so don't spam the user with errors they can't fix!
    
    services = wx.GetApp().GetServicesManager().GetServices( ( HC.LOCAL_BOORU, ) )
    
    for service in services:
        
        info = service.GetInfo()
        
        internal_port = info[ 'port' ]
        upnp = info[ 'upnp' ]
        
        if ( local_ip, internal_port ) in our_mappings:
            
            current_external_port = our_mappings[ ( local_ip, internal_port ) ]
            
            if upnp is None or current_external_port != upnp: HydrusNATPunch.RemoveUPnPMapping( current_external_port, 'TCP' )
            
        
    
    for service in services:
        
        info = service.GetInfo()
        
        internal_port = info[ 'port' ]
        upnp = info[ 'upnp' ]
        
        if upnp is not None:
            
            if ( local_ip, internal_port ) not in our_mappings:
                
                service_type = service.GetServiceType()
                
                external_port = upnp
                
                protocol = 'TCP'
                
                description = HC.service_string_lookup[ service_type ] + ' at ' + local_ip + ':' + str( internal_port )
                
                duration = 3600
                
                HydrusNATPunch.AddUPnPMapping( local_ip, internal_port, external_port, protocol, description, duration = duration )
                
            
        
    