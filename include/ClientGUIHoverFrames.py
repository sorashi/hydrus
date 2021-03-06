from . import ClientConstants as CC
from . import ClientData
from . import ClientGUIDragDrop
from . import ClientGUICanvas
from . import ClientGUICommon
from . import ClientGUICore as CGC
from . import ClientGUIFunctions
from . import ClientGUIListBoxes
from . import ClientGUIMediaControls
from . import ClientGUIMenus
from . import ClientGUIMPV
from . import ClientGUITopLevelWindows
from . import ClientGUIScrolledPanelsEdit
from . import ClientGUIShortcuts
from . import ClientGUIShortcutControls
from . import ClientMedia
from . import HydrusConstants as HC
from . import HydrusData
from . import HydrusGlobals as HG
from . import HydrusSerialisable
import os
from qtpy import QtCore as QC
from qtpy import QtWidgets as QW
from qtpy import QtGui as QG
from . import QtPorting as QP

class FullscreenHoverFrame( QW.QFrame ):
    
    def __init__( self, parent, my_canvas, canvas_key ):
        
        QW.QFrame.__init__( self, parent )
        
        self.setWindowFlags( QC.Qt.FramelessWindowHint | QC.Qt.Tool )
        
        self.setAttribute( QC.Qt.WA_ShowWithoutActivating )
        self.setAttribute( QC.Qt.WA_DeleteOnClose )
        
        self.setFrameStyle( QW.QFrame.Panel | QW.QFrame.Raised )
        self.setLineWidth( 2 )
        
        self._my_canvas = my_canvas
        self._canvas_key = canvas_key
        self._current_media = None
        
        self._always_on_top = False
        
        self._last_ideal_position = None
        
        self.setCursor( QG.QCursor( QC.Qt.ArrowCursor ) )
        
        self._hide_until =  None
        
        self._position_initialised = False
        
        HG.client_controller.sub( self, 'SetDisplayMedia', 'canvas_new_display_media' )
        
        HG.client_controller.gui.RegisterUIUpdateWindow( self )
        
    
    def _GetIdealSizeAndPosition( self ):
        
        raise NotImplementedError()
        
    
    def _SizeAndPosition( self, force = False ):
        
        if self.parentWidget().isVisible() or force:
            
            ( should_resize, my_ideal_size, my_ideal_position ) = self._GetIdealSizeAndPosition()
            
            if should_resize:
                
                self.setGeometry( QC.QRect( my_ideal_position, my_ideal_size ) )
                
            else:
                
                self.move( my_ideal_position )
                
            
            self._position_initialised = True
            
        
    
    def keyPressEvent( self, event ):
        
        # sendEvent here does some shortcutoverride pain in the neck
        
        self._my_canvas.keyPressEvent( event )
        
    
    def SetDisplayMedia( self, canvas_key, media ):
        
        if canvas_key == self._canvas_key:
            
            self._current_media = media
            
        
    
    def TIMERUIUpdate( self ):
        
        if not self._position_initialised:
            
            self._SizeAndPosition()
            
        
        current_focus_tlw = QW.QApplication.activeWindow()
        
        focus_is_on_descendant = ClientGUIFunctions.IsQtAncestor( current_focus_tlw, self._my_canvas.window(), through_tlws = True )
        focus_has_right_window_type = isinstance( current_focus_tlw, ( ClientGUICanvas.CanvasFrame, FullscreenHoverFrame ) )
        
        focus_is_good = focus_is_on_descendant and focus_has_right_window_type
        
        mouse_is_over_self_or_child = False
        
        for tlw in QW.QApplication.topLevelWidgets():
            
            if tlw == self or ClientGUIFunctions.IsQtAncestor( tlw, self, through_tlws = True ):
                
                if tlw.underMouse():
                    
                    mouse_is_over_self_or_child = True
                    
                    break
                    
                
            
        
        new_options = HG.client_controller.new_options
        
        if self._always_on_top:
            
            self._SizeAndPosition()
            
            self.show()
            
            return
            
        
        if self._hide_until is not None:
            
            if HydrusData.TimeHasPassed( self._hide_until ):
                
                self._hide_until =  None
                
            else:
                
                return
                
            
        
        if self._current_media is None or not self._my_canvas.isVisible():
            
            if self.isVisible():
                
                if HG.hover_window_report_mode:
                    
                    HydrusData.ShowText( repr( self ) + ' - hiding because nothing to show or parent hidden.' )
                    
                
                self.hide()
                
            
        else:
            
            mouse_pos = QG.QCursor.pos()
            
            mouse_x = mouse_pos.x()
            mouse_y = mouse_pos.y()
            
            my_size = self.size()
            
            my_width = my_size.width()
            my_height = my_size.height()
            
            my_pos = self.pos()
            
            my_x = my_pos.x()
            my_y = my_pos.y()
            
            ( should_resize, my_ideal_size, my_ideal_pos ) = self._GetIdealSizeAndPosition()
            
            my_ideal_width = my_ideal_size.width()
            my_ideal_height = my_ideal_size.height()
            
            my_ideal_x = my_ideal_pos.x()
            my_ideal_y = my_ideal_pos.y()
            
            if my_ideal_width == -1:
                
                my_ideal_width = max( my_width, 50 )
                
            
            if my_ideal_height == -1:
                
                my_ideal_height = max( my_height, 50 )
                
            
            in_ideal_x = my_ideal_x <= mouse_x <= my_ideal_x + my_ideal_width
            in_ideal_y = my_ideal_y <= mouse_y <= my_ideal_y + my_ideal_height
            
            in_actual_x = my_x <= mouse_x <= my_x + my_width
            in_actual_y = my_y <= mouse_y <= my_y + my_height
            
            # we test both ideal and actual here because setposition is not always honoured by the OS
            # for instance, in some Linux window managers on a fullscreen view, the top taskbar is hidden, but when hover window is shown, it takes focus and causes taskbar to reappear
            # the reappearance shuffles the screen coordinates down a bit so the hover sits +20px y despite wanting to be lined up with the underlying fullscreen viewer
            # wew lad
            
            in_position = ( in_ideal_x or in_actual_x ) and ( in_ideal_y or in_actual_y )
            
            menu_open = CGC.core().MenuIsOpen()
            
            dialog_is_open = ClientGUIFunctions.DialogIsOpen()
            
            mime = self._current_media.GetMime()
            
            mouse_is_near_animation_bar = self._my_canvas.MouseIsNearAnimationBar()
            
            # this used to have the flash media window test to ensure mouse over flash window hid hovers going over it
            mouse_is_over_something_else_important = mouse_is_near_animation_bar
            
            hide_focus_is_good = focus_is_good or current_focus_tlw is None # don't hide if focus is either gone to another problem or temporarily sperging-out due to a click-transition or similar
            
            ready_to_show = in_position and not mouse_is_over_something_else_important and focus_is_good and not dialog_is_open and not menu_open
            ready_to_hide = not menu_open and not mouse_is_over_self_or_child and ( not in_position or dialog_is_open or not hide_focus_is_good )
            
            def get_logic_report_string():
                
                tuples = []
                
                tuples.append( ( 'mouse: ', ( mouse_x, mouse_y ) ) )
                tuples.append( ( 'winpos: ', ( my_x, my_y ) ) )
                tuples.append( ( 'ideal winpos: ', ( my_ideal_x, my_ideal_y ) ) )
                tuples.append( ( 'winsize: ', ( my_width, my_height ) ) )
                tuples.append( ( 'ideal winsize: ', ( my_ideal_width, my_ideal_height ) ) )
                tuples.append( ( 'in position: ', in_position ) )
                tuples.append( ( 'menu open: ', menu_open ) )
                tuples.append( ( 'dialog open: ', dialog_is_open ) )
                tuples.append( ( 'mouse near animation bar: ', mouse_is_near_animation_bar ) )
                tuples.append( ( 'focus is good: ', focus_is_good ) )
                tuples.append( ( 'focus is on descendant: ', focus_is_on_descendant ) )
                tuples.append( ( 'current focus tlw: ', current_focus_tlw ) )
                
                message = os.linesep * 2 + os.linesep.join( ( a + str( b ) for ( a, b ) in tuples ) )
                
                return message
                
            
            if ready_to_show:
                
                self._SizeAndPosition()
                
                if not self.isVisible():
                    
                    if HG.hover_window_report_mode:
                        
                        HydrusData.ShowText( repr( self ) + ' - showing.' + get_logic_report_string() )
                        
                    
                    self.show()
                    
                
            elif ready_to_hide:
                
                if self.isVisible():
                    
                    if HG.hover_window_report_mode:
                        
                        HydrusData.ShowText( repr( self ) + ' - hiding.' + get_logic_report_string() )
                        
                    
                    self.hide()
                    
                
            
        
    
class FullscreenHoverFrameRightDuplicates( FullscreenHoverFrame ):
    
    def __init__( self, parent, my_canvas, canvas_key ):
        
        FullscreenHoverFrame.__init__( self, parent, my_canvas, canvas_key )
        
        self._always_on_top = True
        
        self._current_index_string = ''
        
        self._comparison_media = None
        
        self._trash_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().delete, HG.client_controller.pub, 'canvas_delete', self._canvas_key )
        self._trash_button.setToolTip( 'send to trash' )
        
        menu_items = []
        
        menu_items.append( ( 'normal', 'edit duplicate metadata merge options for \'this is better\'', 'edit what content is merged when you filter files', HydrusData.Call( self._EditMergeOptions, HC.DUPLICATE_BETTER ) ) )
        menu_items.append( ( 'normal', 'edit duplicate metadata merge options for \'same quality\'', 'edit what content is merged when you filter files', HydrusData.Call( self._EditMergeOptions, HC.DUPLICATE_SAME_QUALITY ) ) )
        
        if HG.client_controller.new_options.GetBoolean( 'advanced_mode' ):
            
            menu_items.append( ( 'normal', 'edit duplicate metadata merge options for \'alternates\' (advanced!)', 'edit what content is merged when you filter files', HydrusData.Call( self._EditMergeOptions, HC.DUPLICATE_ALTERNATE ) ) )
            
        
        menu_items.append( ( 'separator', None, None, None ) )
        menu_items.append( ( 'normal', 'edit background lighten/darken switch intensity', 'edit how much the background will brighten or darken as you switch between the pair', self._EditBackgroundSwitchIntensity ) )
        
        self._cog_button = ClientGUICommon.MenuBitmapButton( self, CC.global_pixmaps().cog, menu_items )
        
        close_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().stop, HG.client_controller.pub, 'canvas_close', self._canvas_key )
        close_button.setToolTip( 'close filter' )
        
        self._back_a_pair = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().first, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'duplicate_filter_back' ), self._canvas_key )
        self._back_a_pair.SetToolTipWithShortcuts( 'go back a pair', 'duplicate_filter_back' )
        
        self._previous_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().previous, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'view_previous' ), self._canvas_key )
        self._previous_button.SetToolTipWithShortcuts( 'previous', 'view_previous' )
        
        self._index_text = ClientGUICommon.BetterStaticText( self, 'index' )
        
        self._next_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().next_bmp, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'view_next' ), self._canvas_key )
        self._next_button.SetToolTipWithShortcuts( 'next', 'view next' )
        
        self._skip_a_pair = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().last, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'duplicate_filter_skip' ), self._canvas_key )
        self._skip_a_pair.SetToolTipWithShortcuts( 'show a different pair', 'duplicate_filter_skip' )
        
        command_button_vbox = QP.VBoxLayout()
        
        dupe_boxes = []
        
        dupe_commands = []
        
        dupe_commands.append( ( 'this is better, and delete the other', 'Set that the current file you are looking at is better than the other in the pair, and set the other file to be deleted.', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'duplicate_filter_this_is_better_and_delete_other' ) ) )
        dupe_commands.append( ( 'this is better, but keep both', 'Set that the current file you are looking at is better than the other in the pair, but keep both files.', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'duplicate_filter_this_is_better_but_keep_both' ) ) )
        dupe_commands.append( ( 'they are the same quality', 'Set that the two files are duplicates of very similar quality.', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'duplicate_filter_exactly_the_same' ) ) )
        
        dupe_boxes.append( ( 'they are duplicates', dupe_commands ) )
        
        dupe_commands = []
        
        dupe_commands.append( ( 'they are related alternates', 'Set that the files are not duplicates, but that one is derived from the other or that they are both descendants of a common ancestor.', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'duplicate_filter_alternates' ) ) )
        dupe_commands.append( ( 'they are not related', 'Set that the files are not duplicates or otherwise related--that this potential pair is a false positive match.', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'duplicate_filter_false_positive' ) ) )
        dupe_commands.append( ( 'custom action', 'Choose one of the other actions but customise the merge and delete options for this specific decision.', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'duplicate_filter_custom_action' ) ) )
        
        dupe_boxes.append( ( 'other', dupe_commands ) )
        
        for ( panel_name, dupe_commands ) in dupe_boxes:
            
            button_panel = ClientGUICommon.StaticBox( self, panel_name )
            
            for ( label, tooltip, command ) in dupe_commands:
                
                command_button = ClientGUICommon.BetterButton( button_panel, label, HG.client_controller.pub, 'canvas_application_command', command, self._canvas_key )
                
                command_button.SetToolTipWithShortcuts( tooltip, command.GetData() )
                
                button_panel.Add( command_button, CC.FLAGS_EXPAND_PERPENDICULAR )
                
            
            QP.AddToLayout( command_button_vbox, button_panel, CC.FLAGS_EXPAND_PERPENDICULAR )
            
        
        self._comparison_statements_vbox = QP.VBoxLayout()
        
        self._comparison_statement_names = [ 'filesize', 'resolution', 'ratio', 'mime', 'num_tags', 'time_imported', 'jpeg_quality', 'pixel_duplicates' ]
        
        self._comparison_statements_sts = {}
        
        for name in self._comparison_statement_names:
            
            panel = QW.QWidget( self )
            
            st = ClientGUICommon.BetterStaticText( panel, 'init' )
            
            self._comparison_statements_sts[ name ] = ( panel, st )
            
            hbox = QP.HBoxLayout()
            
            QP.AddToLayout( hbox, (20,20), CC.FLAGS_EXPAND_BOTH_WAYS )
            QP.AddToLayout( hbox, st, CC.FLAGS_VCENTER )
            QP.AddToLayout( hbox, (20,20), CC.FLAGS_EXPAND_BOTH_WAYS )
            
            panel.setLayout( hbox )
            
            panel.setVisible( False )
            
            QP.AddToLayout( self._comparison_statements_vbox, panel, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
            
        
        
        #
        
        top_button_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( top_button_hbox, self._trash_button, CC.FLAGS_VCENTER )
        QP.AddToLayout( top_button_hbox, self._cog_button, CC.FLAGS_VCENTER )
        QP.AddToLayout( top_button_hbox, close_button, CC.FLAGS_VCENTER )
        
        navigation_button_hbox = QP.HBoxLayout()
        
        QP.AddToLayout( navigation_button_hbox, self._back_a_pair, CC.FLAGS_VCENTER )
        QP.AddToLayout( navigation_button_hbox, self._previous_button, CC.FLAGS_VCENTER )
        QP.AddToLayout( navigation_button_hbox, (20,20), CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( navigation_button_hbox, self._index_text, CC.FLAGS_VCENTER )
        QP.AddToLayout( navigation_button_hbox, (20,20), CC.FLAGS_EXPAND_BOTH_WAYS )
        QP.AddToLayout( navigation_button_hbox, self._next_button, CC.FLAGS_VCENTER )
        QP.AddToLayout( navigation_button_hbox, self._skip_a_pair, CC.FLAGS_VCENTER )
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, navigation_button_hbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        QP.AddToLayout( vbox, top_button_hbox, CC.FLAGS_BUTTON_SIZER )
        QP.AddToLayout( vbox, command_button_vbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        QP.AddToLayout( vbox, self._comparison_statements_vbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        self.setLayout( vbox )
        
        HG.client_controller.sub( self, 'SetDuplicatePair', 'canvas_new_duplicate_pair' )
        HG.client_controller.sub( self, 'SetIndexString', 'canvas_new_index_string' )
        
    
    def _EditBackgroundSwitchIntensity( self ):
        
        new_options = HG.client_controller.new_options
        
        value = new_options.GetNoneableInteger( 'duplicate_background_switch_intensity' )
        
        with ClientGUITopLevelWindows.DialogEdit( self, 'edit lighten/darken intensity' ) as dlg:
            
            panel = ClientGUIScrolledPanelsEdit.EditNoneableIntegerPanel( dlg, value, message = 'intensity: ', none_phrase = 'do not change', min = 1, max = 9 )
            
            dlg.SetPanel( panel )
            
            if dlg.exec() == QW.QDialog.Accepted:
                
                new_value = panel.GetValue()
                
                new_options.SetNoneableInteger( 'duplicate_background_switch_intensity', new_value )
                
            
        
    
    def _EditMergeOptions( self, duplicate_type ):
        
        new_options = HG.client_controller.new_options
        
        duplicate_action_options = new_options.GetDuplicateActionOptions( duplicate_type )
        
        with ClientGUITopLevelWindows.DialogEdit( self, 'edit duplicate merge options' ) as dlg:
            
            panel = ClientGUIScrolledPanelsEdit.EditDuplicateActionOptionsPanel( dlg, duplicate_type, duplicate_action_options )
            
            dlg.SetPanel( panel )
            
            if dlg.exec() == QW.QDialog.Accepted:
                
                duplicate_action_options = panel.GetValue()
                
                new_options.SetDuplicateActionOptions( duplicate_type, duplicate_action_options )
                
            
        
    
    def _GetIdealSizeAndPosition( self ):
        
        parent_window = self.parentWidget().window()
        
        parent_size = parent_window.size()
        
        parent_width = parent_size.width()
        parent_height = parent_size.height()
        
        my_size = self.size()
        
        my_width = my_size.width()
        my_height = my_size.height()
        
        my_ideal_width = int( parent_width * 0.2 )
        my_ideal_height = self.minimumSizeHint().height()
        
        should_resize = my_ideal_width != my_width or my_ideal_height != my_height
        
        ideal_size = QC.QSize( my_ideal_width, my_ideal_height )
        ideal_position = ClientGUIFunctions.ClientToScreen( parent_window, QC.QPoint( int( parent_width - my_ideal_width ), int( parent_height * 0.3 ) ) )
        
        return ( should_resize, ideal_size, ideal_position )
        
    
    def _ResetComparisonStatements( self ):
        
        statements_and_scores = ClientMedia.GetDuplicateComparisonStatements( self._current_media, self._comparison_media )
        
        for name in self._comparison_statement_names:
            
            ( panel, st ) = self._comparison_statements_sts[ name ]
            
            if name in statements_and_scores:
                
                ( statement, score ) = statements_and_scores[ name ]
                
                if not panel.isVisible():
                    
                    panel.show()
                    
                
                st.setText( statement )
                
                if score > 0:
                    
                    colour = ( 0, 128, 0 )
                    
                elif score < 0:
                    
                    colour = ( 128, 0, 0 )
                    
                else:
                    
                    colour = ( 0, 0, 128 )
                    
                
                QP.SetForegroundColour( st, colour )
                
            else:
                
                if panel.isVisible():
                    
                    panel.hide()
            
        
    
    def wheelEvent( self, event ):
        
        QW.QApplication.sendEvent( self.parentWidget(), event )
        
    
    def SetDuplicatePair( self, canvas_key, shown_media, comparison_media ):
        
        if canvas_key == self._canvas_key:
            
            self._current_media = shown_media
            self._comparison_media = comparison_media
            
            self._ResetComparisonStatements()
            
            # minimumsize is not immediately updated without this
            self.layout().activate()
            
            self._SizeAndPosition( force = True )
            
        
    
    def SetIndexString( self, canvas_key, text ):
        
        if canvas_key == self._canvas_key:
            
            self._current_index_string = text
            
            self._index_text.setText( self._current_index_string )
            
        
    
class FullscreenHoverFrameTop( FullscreenHoverFrame ):
    
    def __init__( self, parent, my_canvas, canvas_key ):
        
        FullscreenHoverFrame.__init__( self, parent, my_canvas, canvas_key )
        
        self._current_zoom = 1.0
        self._current_index_string = ''
        
        self._top_hbox = QP.HBoxLayout()
        self._top_hbox.setContentsMargins( 0, 0, 0, 2 )
        
        self._title_text = ClientGUICommon.BetterStaticText( self, 'title', ellipsize_end = True )
        self._info_text = ClientGUICommon.BetterStaticText( self, 'info', ellipsize_end = True )
        
        self._title_text.setAlignment( QC.Qt.AlignHCenter | QC.Qt.AlignVCenter )
        self._info_text.setAlignment( QC.Qt.AlignHCenter | QC.Qt.AlignVCenter )
        
        self._PopulateLeftButtons()
        QP.AddToLayout( self._top_hbox, (10,10), CC.FLAGS_EXPAND_BOTH_WAYS )
        self._PopulateCenterButtons()
        QP.AddToLayout( self._top_hbox, (10,10), CC.FLAGS_EXPAND_BOTH_WAYS )
        self._PopulateRightButtons()
        
        vbox = QP.VBoxLayout()
        
        QP.AddToLayout( vbox, self._top_hbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        QP.AddToLayout( vbox, self._title_text, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._info_text, CC.FLAGS_EXPAND_PERPENDICULAR )
        
        self.setLayout( vbox )
        
        HG.client_controller.sub( self, 'ProcessContentUpdates', 'content_updates_gui' )
        HG.client_controller.sub( self, 'SetCurrentZoom', 'canvas_new_zoom' )
        HG.client_controller.sub( self, 'SetIndexString', 'canvas_new_index_string' )
        
    
    def _Archive( self ):
        
        if self._current_media.HasInbox():
            
            command = ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'archive_file' )
            
        else:
            
            command = ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'inbox_file' )
            
        
        HG.client_controller.pub( 'canvas_application_command', command, self._canvas_key )
        
    
    def _GetIdealSizeAndPosition( self ):
        
        # clip this and friends to availableScreenGeometry for size and position, not rely 100% on parent
        
        parent_window = self.parentWidget().window()
        
        parent_size = parent_window.size()
        
        parent_width = parent_size.width()
        
        my_size = self.size()
        
        my_width = my_size.width()
        my_height = my_size.height()
        
        my_ideal_width = int( parent_width * 0.6 )
        
        my_ideal_height = self.sizeHint().height()
        
        should_resize = my_ideal_width != my_width or my_ideal_height != my_height
        
        ideal_size = QC.QSize( my_ideal_width, my_ideal_height )
        ideal_position = ClientGUIFunctions.ClientToScreen( parent_window, QC.QPoint( int( parent_width * 0.2 ), 0 ) )
        
        return ( should_resize, ideal_size, ideal_position )
        
    
    def _ManageShortcuts( self ):
        
        with ClientGUITopLevelWindows.DialogManage( self, 'manage shortcuts' ) as dlg:
            
            panel = ClientGUIShortcutControls.ManageShortcutsPanel( dlg )
            
            dlg.SetPanel( panel )
            
            dlg.exec()
            
        
    
    def _PopulateCenterButtons( self ):
        
        self._archive_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().archive, self._Archive )
        
        self._trash_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().delete, HG.client_controller.pub, 'canvas_delete', self._canvas_key )
        self._trash_button.setToolTip( 'send to trash' )
        
        self._delete_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().trash_delete, HG.client_controller.pub, 'canvas_delete', self._canvas_key )
        self._delete_button.setToolTip( 'delete completely' )
        
        self._undelete_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().undelete, HG.client_controller.pub, 'canvas_undelete', self._canvas_key )
        self._undelete_button.setToolTip( 'undelete' )
        
        QP.AddToLayout( self._top_hbox, self._archive_button, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, self._trash_button, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, self._delete_button, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, self._undelete_button, CC.FLAGS_VCENTER )
        
    
    def _PopulateLeftButtons( self ):
        
        self._index_text = ClientGUICommon.BetterStaticText( self, 'index' )
        
        QP.AddToLayout( self._top_hbox, self._index_text, CC.FLAGS_VCENTER )
        
    
    def _PopulateRightButtons( self ):
        
        self._zoom_text = ClientGUICommon.BetterStaticText( self, 'zoom' )
        
        zoom_in = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().zoom_in, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'zoom_in' ), self._canvas_key )
        zoom_in.SetToolTipWithShortcuts( 'zoom in', 'zoom_in' )
        
        zoom_out = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().zoom_out, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'zoom_out' ), self._canvas_key )
        zoom_out.SetToolTipWithShortcuts( 'zoom out', 'zoom_out' )
        
        zoom_switch = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().zoom_switch, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'switch_between_100_percent_and_canvas_zoom' ), self._canvas_key )
        zoom_switch.SetToolTipWithShortcuts( 'zoom switch', 'switch_between_100_percent_and_canvas_zoom' )
        
        self._volume_control = ClientGUIMediaControls.VolumeControl( self, ClientGUICommon.CANVAS_MEDIA_VIEWER )
        
        if not ClientGUIMPV.MPV_IS_AVAILABLE:
            
            self._volume_control.hide()
            
        
        shortcuts = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().keyboard, self._ShowShortcutMenu )
        shortcuts.setToolTip( 'shortcuts' )
        
        fullscreen_switch = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().fullscreen_switch, HG.client_controller.pub, 'canvas_fullscreen_switch', self._canvas_key )
        fullscreen_switch.setToolTip( 'fullscreen switch' )
        
        if HC.PLATFORM_MACOS:
            
            fullscreen_switch.hide()
            
        
        open_externally = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().open_externally, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'open_file_in_external_program' ), self._canvas_key )
        open_externally.SetToolTipWithShortcuts( 'open externally', 'open_file_in_external_program' )
        
        drag_button = QW.QPushButton( self )
        drag_button.setIcon( QG.QIcon( CC.global_pixmaps().drag ) )
        drag_button.setIconSize( CC.global_pixmaps().drag.size() )
        drag_button.setToolTip( 'drag from here to export file' )
        drag_button.pressed.connect( self.EventDragButton )
        
        close = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().stop, HG.client_controller.pub, 'canvas_close', self._canvas_key )
        close.setToolTip( 'close' )
        
        QP.AddToLayout( self._top_hbox, self._zoom_text, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, zoom_in, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, zoom_out, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, zoom_switch, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, self._volume_control, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, shortcuts, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, fullscreen_switch, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, open_externally, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, drag_button, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, close, CC.FLAGS_VCENTER )
        
    
    def _ResetArchiveButton( self ):
        
        if self._current_media.HasInbox():
            
            ClientGUIFunctions.SetBitmapButtonBitmap( self._archive_button, CC.global_pixmaps().archive )
            self._archive_button.setToolTip( 'archive' )
            
        else:
            
            ClientGUIFunctions.SetBitmapButtonBitmap( self._archive_button, CC.global_pixmaps().to_inbox )
            
            self._archive_button.setToolTip( 'return to inbox' )
            
        
    
    def _ResetButtons( self ):
        
        if self._current_media is not None:
            
            self._ResetArchiveButton()
            
            current_locations = self._current_media.GetLocationsManager().GetCurrent()
            
            if CC.LOCAL_FILE_SERVICE_KEY in current_locations:
                
                self._trash_button.show()
                self._delete_button.hide()
                self._undelete_button.hide()
                
            elif CC.TRASH_SERVICE_KEY in current_locations:
                
                self._trash_button.hide()
                self._delete_button.show()
                self._undelete_button.show()
                
            
        
    
    def _ResetText( self ):
        
        if self._current_media is None:
            
            self._title_text.hide()
            self._info_text.hide()
            
        else:
            
            label = self._current_media.GetTitleString()
            
            if len( label ) > 0:
                
                self._title_text.setText( label )
                
                self._title_text.show()
                
            else: self._title_text.hide()
            
            lines = self._current_media.GetPrettyInfoLines()
            
            label = ' | '.join( lines )
            
            self._info_text.setText( label )
            
            self._info_text.show()
            
        
    
    def _FlipActiveDefaultCustomShortcut( self, name ):
        
        new_options = HG.client_controller.new_options
        
        default_media_viewer_custom_shortcuts = list( new_options.GetStringList( 'default_media_viewer_custom_shortcuts' ) )
        
        if name in default_media_viewer_custom_shortcuts:
            
            default_media_viewer_custom_shortcuts.remove( name )
            
        else:
            
            default_media_viewer_custom_shortcuts.append( name )
            
            default_media_viewer_custom_shortcuts.sort()
            
        
        new_options.SetStringList( 'default_media_viewer_custom_shortcuts', default_media_viewer_custom_shortcuts )
        
    
    def _ShowShortcutMenu( self ):
        
        all_shortcut_names = HG.client_controller.Read( 'serialisable_names', HydrusSerialisable.SERIALISABLE_TYPE_SHORTCUT_SET )
        
        custom_shortcuts_names = [ name for name in all_shortcut_names if name not in ClientGUIShortcuts.SHORTCUTS_RESERVED_NAMES ]
        
        menu = QW.QMenu()

        ClientGUIMenus.AppendMenuItem( menu, 'edit shortcuts', 'edit your sets of shortcuts, and change what shortcuts are currently active on this media viewer', self._ManageShortcuts )
        
        if len( custom_shortcuts_names ) > 0:
            
            my_canvas_active_custom_shortcuts = self._my_canvas.GetActiveCustomShortcutNames()
            default_media_viewer_custom_shortcuts = HG.client_controller.new_options.GetStringList( 'default_media_viewer_custom_shortcuts' )
            
            current_menu = QW.QMenu( menu )
            
            for name in custom_shortcuts_names:
                
                ClientGUIMenus.AppendMenuCheckItem( current_menu, name, 'turn this shortcut set on/off', name in my_canvas_active_custom_shortcuts, self._my_canvas.FlipActiveCustomShortcutName, name )
                
            
            ClientGUIMenus.AppendMenu( menu, current_menu, 'set current shortcuts' )
            
            defaults_menu = QW.QMenu( menu )
            
            for name in custom_shortcuts_names:
                
                ClientGUIMenus.AppendMenuCheckItem( defaults_menu, name, 'turn this shortcut set on/off by default', name in default_media_viewer_custom_shortcuts, self._FlipActiveDefaultCustomShortcut, name )
                
            
            ClientGUIMenus.AppendMenu( menu, defaults_menu, 'set default shortcuts' )
            
        
        CGC.core().PopupMenu( self, menu )
        
    
    def EventDragButton( self ):
        
        if self._current_media is None:
            
            return True # was: event.ignore()
            
        
        page_key = None
        
        media = [ self._current_media ]
        
        alt_down = QW.QApplication.keyboardModifiers() & QC.Qt.AltModifier
        
        result = ClientGUIDragDrop.DoFileExportDragDrop( self, page_key, media, alt_down )
        
        if result != QC.Qt.IgnoreAction:
            
            HG.client_controller.pub( 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'pause_media' ), self._canvas_key )
            
        
    
    def resizeEvent( self, event ):
        
        # reset wrap width
        self._ResetText()
        
        event.ignore()
        
    
    def wheelEvent( self, event ):
        
        QW.QApplication.sendEvent( self.parentWidget(), event )
        
    
    def ProcessContentUpdates( self, service_keys_to_content_updates ):
        
        if self._current_media is not None:
            
            my_hash = self._current_media.GetHash()
            
            do_redraw = False
            
            for ( service_key, content_updates ) in list(service_keys_to_content_updates.items()):
                
                if True in ( my_hash in content_update.GetHashes() for content_update in content_updates ):
                    
                    do_redraw = True
                    
                    break
                    
                
            
            if do_redraw:
                
                self._ResetButtons()
                
            
        
    
    def SetCurrentZoom( self, canvas_key, zoom ):
        
        if canvas_key == self._canvas_key:
            
            self._current_zoom = zoom
            
            label = ClientData.ConvertZoomToPercentage( self._current_zoom )
            
            self._zoom_text.setText( label )
            
        
    
    def SetDisplayMedia( self, canvas_key, media ):
        
        if canvas_key == self._canvas_key:
            
            FullscreenHoverFrame.SetDisplayMedia( self, canvas_key, media )
            
            self._ResetText()
            
            self._ResetButtons()
            
            # minimumsize is not immediately updated without this
            self.layout().activate()
            
            self._SizeAndPosition( force = True )
            
        
    
    def SetIndexString( self, canvas_key, text ):
        
        if canvas_key == self._canvas_key:
            
            self._current_index_string = text
            
            self._index_text.setText( self._current_index_string )
            
        
    
class FullscreenHoverFrameTopArchiveDeleteFilter( FullscreenHoverFrameTop ):
    
    def _Archive( self ):
        
        HG.client_controller.pub( 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'archive_file' ), self._canvas_key )
        
    
    def _PopulateLeftButtons( self ):
        
        self._back_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().previous, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'archive_delete_filter_back' ), self._canvas_key )
        self._back_button.SetToolTipWithShortcuts( 'back', 'archive_delete_filter_back' )
        
        QP.AddToLayout( self._top_hbox, self._back_button, CC.FLAGS_VCENTER )
        
        FullscreenHoverFrameTop._PopulateLeftButtons( self )
        
        self._skip_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().next_bmp, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'archive_delete_filter_skip' ), self._canvas_key )
        self._skip_button.SetToolTipWithShortcuts( 'skip', 'archive_delete_filter_skip' )
        
        QP.AddToLayout( self._top_hbox, self._skip_button, CC.FLAGS_VCENTER )
        
    
    def _ResetArchiveButton( self ):
        
        ClientGUIFunctions.SetBitmapButtonBitmap( self._archive_button, CC.global_pixmaps().archive )
        self._archive_button.setToolTip( 'archive' )
        
    
class FullscreenHoverFrameTopNavigable( FullscreenHoverFrameTop ):
    
    def _PopulateLeftButtons( self ):
        
        self._previous_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().previous, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'view_previous' ), self._canvas_key )
        self._previous_button.SetToolTipWithShortcuts( 'previous', 'view_previous' )
        
        self._index_text = ClientGUICommon.BetterStaticText( self, 'index' )
        
        self._next_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().next_bmp, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'view_next' ), self._canvas_key )
        self._next_button.SetToolTipWithShortcuts( 'next', 'view_next' )
        
        QP.AddToLayout( self._top_hbox, self._previous_button, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, self._index_text, CC.FLAGS_VCENTER )
        QP.AddToLayout( self._top_hbox, self._next_button, CC.FLAGS_VCENTER )
        
    
class FullscreenHoverFrameTopDuplicatesFilter( FullscreenHoverFrameTopNavigable ):
    
    def _PopulateLeftButtons( self ):
        
        self._first_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().first, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'duplicate_filter_back' ), self._canvas_key )
        self._first_button.SetToolTipWithShortcuts( 'go back a pair', 'duplicate_filter_back' )
        
        QP.AddToLayout( self._top_hbox, self._first_button, CC.FLAGS_VCENTER )
        
        FullscreenHoverFrameTopNavigable._PopulateLeftButtons( self )
        
        self._last_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().last, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'duplicate_filter_skip' ), self._canvas_key )
        self._last_button.SetToolTipWithShortcuts( 'show a different pair', 'duplicate_filter_skip' )
        
        QP.AddToLayout( self._top_hbox, self._last_button, CC.FLAGS_VCENTER )
        
    
class FullscreenHoverFrameTopNavigableList( FullscreenHoverFrameTopNavigable ):
    
    def _PopulateLeftButtons( self ):
        
        self._first_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().first, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'view_first' ), self._canvas_key )
        self._first_button.SetToolTipWithShortcuts( 'first', 'view_first' )
        
        QP.AddToLayout( self._top_hbox, self._first_button, CC.FLAGS_VCENTER )
        
        FullscreenHoverFrameTopNavigable._PopulateLeftButtons( self )
        
        self._last_button = ClientGUICommon.BetterBitmapButton( self, CC.global_pixmaps().last, HG.client_controller.pub, 'canvas_application_command', ClientData.ApplicationCommand( CC.APPLICATION_COMMAND_TYPE_SIMPLE, 'view_last' ), self._canvas_key )
        self._last_button.SetToolTipWithShortcuts( 'last', 'view_last' )
        
        QP.AddToLayout( self._top_hbox, self._last_button, CC.FLAGS_VCENTER )
        
    
class FullscreenHoverFrameTopRight( FullscreenHoverFrame ):
    
    def __init__( self, parent, my_canvas, canvas_key ):
        
        FullscreenHoverFrame.__init__( self, parent, my_canvas, canvas_key )
        
        vbox = QP.VBoxLayout()
        
        self._icon_panel = QW.QWidget( self )
        
        self._trash_icon = ClientGUICommon.BufferedWindowIcon( self._icon_panel, CC.global_pixmaps().trash )
        self._inbox_icon = ClientGUICommon.BufferedWindowIcon( self._icon_panel, CC.global_pixmaps().inbox )
        
        icon_hbox = QP.HBoxLayout( spacing = 0 )
        
        QP.AddToLayout( icon_hbox, (16,16), CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        QP.AddToLayout( icon_hbox, self._trash_icon, CC.FLAGS_VCENTER )
        QP.AddToLayout( icon_hbox, self._inbox_icon, CC.FLAGS_VCENTER )
        
        self._icon_panel.setLayout( icon_hbox )
        
        # repo strings
        
        self._file_repos = QP.MakeQLabelWithAlignment( '', self, QC.Qt.AlignRight | QC.Qt.AlignVCenter )
        
        # urls
        
        self._last_seen_urls = []
        self._urls_vbox = QP.VBoxLayout()
        
        # likes
        
        like_hbox = QP.HBoxLayout( spacing = 0 )
        
        like_services = HG.client_controller.services_manager.GetServices( ( HC.LOCAL_RATING_LIKE, ) )
        
        if len( like_services ) > 0:
            
            QP.AddToLayout( like_hbox, ( 16, 16 ), CC.FLAGS_EXPAND_BOTH_WAYS )
            
        
        for service in like_services:
            
            service_key = service.GetServiceKey()
            
            control = ClientGUICommon.RatingLikeCanvas( self, service_key, canvas_key )
            
            QP.AddToLayout( like_hbox, control, CC.FLAGS_NONE )
            
        
        # each numerical one in turn
        
        QP.AddToLayout( vbox, like_hbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        
        numerical_services = HG.client_controller.services_manager.GetServices( ( HC.LOCAL_RATING_NUMERICAL, ) )
        
        for service in numerical_services:
            
            service_key = service.GetServiceKey()
            
            control = ClientGUICommon.RatingNumericalCanvas( self, service_key, canvas_key )
            
            hbox = QP.HBoxLayout( spacing = 0 )
            
            QP.AddToLayout( hbox, ( 16, 16 ), CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
            QP.AddToLayout( hbox, control, CC.FLAGS_NONE )
            
            QP.AddToLayout( vbox, hbox, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
            
        
        QP.AddToLayout( vbox, self._icon_panel, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        QP.AddToLayout( vbox, self._file_repos, CC.FLAGS_EXPAND_PERPENDICULAR )
        QP.AddToLayout( vbox, self._urls_vbox, CC.FLAGS_EXPAND_SIZER_PERPENDICULAR )
        
        vbox.addStretch( 1 )
        self.setLayout( vbox )
        
        self._ResetData()
        
        HG.client_controller.sub( self, 'ProcessContentUpdates', 'content_updates_gui' )
        
    
    def _GetIdealSizeAndPosition( self ):
        
        parent_window = self.parentWidget().window()
        
        parent_size = parent_window.size()
        
        parent_width = parent_size.width()
        
        my_size = self.size()
        
        my_width = my_size.width()
        my_height = my_size.height()
        
        my_ideal_width = int( parent_width * 0.2 )
        
        my_ideal_height = self.minimumSizeHint().height()
        
        should_resize = my_ideal_width != my_width or my_ideal_height != my_height
        
        ideal_size = QC.QSize( my_ideal_width, my_ideal_height )
        ideal_position = ClientGUIFunctions.ClientToScreen( parent_window, QC.QPoint( int( parent_width - my_ideal_width ), 0 ) )
        
        return ( should_resize, ideal_size, ideal_position )
        
    
    def _ResetData( self ):
        
        if self._current_media is not None:
            
            has_inbox = self._current_media.HasInbox()
            has_trash = CC.TRASH_SERVICE_KEY in self._current_media.GetLocationsManager().GetCurrent()
            
            if has_inbox or has_trash:
                
                self._icon_panel.show()
                
                if has_inbox:
                    
                    self._inbox_icon.show()
                    
                else:
                    
                    self._inbox_icon.hide()
                    
                
                if has_trash:
                    
                    self._trash_icon.show()
                    
                else:
                    
                    self._trash_icon.hide()
                    
                
            else:
                
                self._icon_panel.setVisible( False )
                
            
            remote_strings = self._current_media.GetLocationsManager().GetRemoteLocationStrings()
            
            if len( remote_strings ) == 0:
                
                self._file_repos.hide()
                
            else:
                
                remote_string = os.linesep.join( remote_strings )
                
                self._file_repos.setText( remote_string )
                
                self._file_repos.show()
                
            
            # urls
            
            urls = self._current_media.GetLocationsManager().GetURLs()
            
            if urls != self._last_seen_urls:
                
                self._last_seen_urls = list( urls )
                
                QP.ClearLayout( self._urls_vbox, delete_widgets = True )
                
                url_tuples = HG.client_controller.network_engine.domain_manager.ConvertURLsToMediaViewerTuples( urls )
                
                for ( display_string, url ) in url_tuples:
                    
                    link = ClientGUICommon.BetterHyperLink( self, display_string, url )
                    
                    QP.AddToLayout( self._urls_vbox, link, CC.FLAGS_EXPAND_PERPENDICULAR )
                    
                    self.layout().addStretch( 1 )
                    
                
            
        
        self._SizeAndPosition()
        
    
    def wheelEvent( self, event ):
        
        QW.QApplication.sendEvent( self.parentWidget(), event )
        
    
    def ProcessContentUpdates( self, service_keys_to_content_updates ):
        
        if self._current_media is not None:
            
            my_hash = self._current_media.GetHash()
            
            do_redraw = False
            
            for ( service_key, content_updates ) in list(service_keys_to_content_updates.items()):
                
                # ratings updates do not change the shape of this hover but file changes of several kinds do
                
                if True in ( my_hash in content_update.GetHashes() for content_update in content_updates if content_update.GetDataType() == HC.CONTENT_TYPE_FILES ):
                    
                    do_redraw = True
                    
                    break
                    
                
            
            if do_redraw:
                
                self._ResetData()
                
            
        
    
    def SetDisplayMedia( self, canvas_key, media ):
        
        if canvas_key == self._canvas_key:
            
            FullscreenHoverFrame.SetDisplayMedia( self, canvas_key, media )
            
            self._ResetData()
            
            # minimumsize is not immediately updated without this
            self.layout().activate()
            
            self._SizeAndPosition( force = True )
            
        
    
class FullscreenHoverFrameTags( FullscreenHoverFrame ):
    
    def __init__( self, parent, my_canvas, canvas_key ):
        
        FullscreenHoverFrame.__init__( self, parent, my_canvas, canvas_key )
        
        vbox = QP.VBoxLayout()
        
        self._tags = ClientGUIListBoxes.ListBoxTagsSelectionHoverFrame( self, self._canvas_key )
        
        QP.AddToLayout( vbox, self._tags, CC.FLAGS_EXPAND_SIZER_BOTH_WAYS )
        
        self.setLayout( vbox )
        
        HG.client_controller.sub( self, 'ProcessContentUpdates', 'content_updates_gui' )
        
    
    def _GetIdealSizeAndPosition( self ):
        
        parent_window = self.parentWidget().window()
        
        parent_size = parent_window.size()
        
        parent_width = parent_size.width()
        parent_height = parent_size.height()
        
        my_size = self.size()
        
        my_width = my_size.width()
        my_height = my_size.height()
        
        my_ideal_width = int( parent_width * 0.2 )
        
        my_ideal_height = parent_height
        
        should_resize = my_ideal_width != my_width or my_ideal_height != my_height
        
        ideal_size = QC.QSize( my_ideal_width, my_ideal_height )
        ideal_position = ClientGUIFunctions.ClientToScreen( parent_window, QC.QPoint( 0, 0 ) )
        
        return ( should_resize, ideal_size, ideal_position )
        
    
    def _ResetTags( self ):
        
        if self._current_media is not None:
            
            self._tags.SetTagsByMedia( [ self._current_media ], force_reload = True )
            
        
    
    def ProcessContentUpdates( self, service_keys_to_content_updates ):
        
        if self._current_media is not None:
            
            my_hash = self._current_media.GetHash()
            
            do_redraw = False
            
            for ( service_key, content_updates ) in list(service_keys_to_content_updates.items()):
                
                if True in ( my_hash in content_update.GetHashes() for content_update in content_updates ):
                    
                    do_redraw = True
                    
                    break
                    
                
            
            if do_redraw:
                
                self._ResetTags()
                
            
        
    
    def SetDisplayMedia( self, canvas_key, media ):
        
        if canvas_key == self._canvas_key:
            
            FullscreenHoverFrame.SetDisplayMedia( self, canvas_key, media )
            
            self._ResetTags()
            
        
    
