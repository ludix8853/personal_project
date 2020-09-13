'''
@author: Sebastian Lapuschkin
@author: Gregoire Montavon
@maintainer: Sebastian Lapuschkin
@contact: sebastian.lapuschkin@hhi.fraunhofer.de, wojciech.samek@hhi.fraunhofer.de
@date: 20.10.2015
@version: 1.2+
@copyright: Copyright (c)  2015-2017, Sebastian Lapuschkin, Alexander Binder, Gregoire Montavon, Klaus-Robert Mueller, Wojciech Samek
@license : BSD-2-Clause
'''
import data_io
from .module import Module
import numpy
import numpy as np
import importlib.util as imp
import time
if imp.find_spec("cupy"):
    import cupy
    import cupy as np
na = np.newaxis
from config import *

# logger = get_logger(os.path.basename('record'))

# -------------------------------
# 2D Convolution layer
# -------------------------------

class Convolution(Module):

    def __init__(self, filtersize=(5,5,3,32), stride = (2,2)):
        '''
        Constructor for a Convolution layer.

        Parameters
        ----------

        filtersize : 4-tuple with values (h,w,d,n), where
            h = filter heigth
            w = filter width
            d = filter depth
            n = number of filters = number of outputs

        stride : 2-tuple (h,w), where
            h = step size for filter application in vertical direction
            w = step size in horizontal direction

        '''

        Module.__init__(self)

        self.fh, self.fw, self.fd, self.n = filtersize
        self.stride = stride


        self.W = np.random.normal(0,1./(self.fh*self.fw*self.fd)**.5, filtersize)
        self.B = np.zeros([self.n])

    def to_cupy(self):
        global np
        assert imp.find_spec("cupy"), "module cupy not found."
        self.W = cupy.array(self.W)
        self.B = cupy.array(self.B)
        if hasattr(self, 'X') and self.X is not None: self.X = cupy.array(self.X)
        if hasattr(self, 'Y') and self.Y is not None: self.Y = cupy.array(self.Y)
        if hasattr(self, 'Z') and self.Z is not None: self.Z = cupy.array(self.Z)
        if hasattr(self, 'DY') and self.DY is not None: self.DY = cupy.array(self.DY)
        np = cupy

    def to_numpy(self):
        global np
        if not imp.find_spec("cupy"):
            pass #nothing to do if there is no cupy. model should exist as numpy arrays
        else:
            self.W = cupy.asnumpy(self.W)
            self.B = cupy.asnumpy(self.B)
            if hasattr(self, 'X') and self.X is not None: self.X = cupy.asnumpy(self.X)
            if hasattr(self, 'Y') and self.Y is not None: self.Y = cupy.asnumpy(self.Y)
            if hasattr(self, 'Z') and self.Z is not None: self.Z = cupy.asnumpy(self.Z)
            if hasattr(self, 'DY') and self.DY is not None: self.DY = cupy.asnumpy(self.DY)
            np = numpy

    def forward(self,X,lrp_aware=False):
        '''
        Realizes the forward pass of an input through the convolution layer.

        Parameters
        ----------
        X : numpy.ndarray
            a network input, shaped (N,H,W,D), with
            N = batch size
            H, W, D = input size in heigth, width, depth

        lrp_aware : bool
            controls whether the forward pass is to be computed with awareness for multiple following
            LRP calls. this will sacrifice speed in the forward pass but will save time if multiple LRP
            calls will follow for the current X, e.g. wit different parameter settings or for multiple
            target classes.

        Returns
        -------
        Y : numpy.ndarray
            the layer outputs.
        '''

        self.lrp_aware = lrp_aware
        self.X = X
        N,H,W,D = X.shape
#         logger.info("=======================Conv Check===============================")
#         logger.info("the conv X shape is {0}".format(X.shape))
#         logger.info("the conv X shape value is : {0}".format(np.sum(~np.isnan(X))))
#         logger.info("the conv filter size is ({},{},{},{})".format(self.fh, self.fw, self.fd, self.n))

        hf, wf, df, nf  = self.W.shape
#         logger.info("the conv W shape is {0}".format(self.W.shape))
#         logger.info("the conv W shape value is : {0}".format(np.sum(~np.isnan(self.W))))
        hstride, wstride = self.stride
#         logger.info("the conv stride shape is {0}".format(self.stride))
        numfilters = self.n
#         logger.info("the number of filter is {}".format(numfilters))

        #assume the given pooling and stride parameters are carefully chosen.
        Hout = (H - hf) // hstride + 1
        Wout = (W - wf) // wstride + 1
#         logger.info("{} : {}, {} : {} ".format('H',Hout,'W', Wout))
        


        #initialize pooled output
        self.Y = np.zeros((N,Hout,Wout,numfilters))
        if self.lrp_aware:
            self.Z = np.zeros((N, Hout, Wout, hf, wf, df, nf)) #initialize container for precomputed forward messages
            for i in range(Hout):
                for j in range(Wout):
                    self.Z[:,i,j,...] = self.W[na,...] * self.X[:, i*hstride:i*hstride+hf , j*wstride:j*wstride+wf , : , na] # N, hf, wf, df, nf
                    self.Y[:,i,j,:] = self.Z[:,i,j,...].sum(axis=(1,2,3)) + self.B
        else:
            for i in range(Hout):
                for j in range(Wout):
                    self.Y[:,i,j,:] = np.tensordot(X[:, i*hstride:i*hstride+hf: , j*wstride:j*wstride+wf: , : ],self.W,axes = ([1,2,3],[0,1,2])) + self.B

#         logger.info("after conv tensordot W is {0}".format(self.W.shape))
#         logger.info("after conv tensordot W  shape value is : {0}".format(np.sum(~np.isnan(self.W))))
        
#         logger.info("after conv tensordot shape is {0}".format(self.X.shape))
#         logger.info("after conv tensordot X shape value is : {0}".format(np.sum(~np.isnan(self.X))))
        input_check = '../r_array/conv_input({},{},{}).npy'.format(self.X.shape[0],self.X.shape[1],self.X.shape[2])
        data_io.write(self.X, input_check)
        
#         logger.info("after conv checking tensordot shape is {0}".format(X.shape))
#         logger.info("after conv checking tensordot X shape value is : {0}".format(np.sum(~np.isnan(X))))
        kind_check = '../r_array/conv_check_input({},{},{}).npy'.format(X.shape[0],X.shape[1],X.shape[2])
        data_io.write(X, kind_check)
        
#         logger.info("the conv output of shape is {0}".format(self.Y.shape))
#         logger.info("after conv checking output shape value is : {0}".format(np.sum(~np.isnan(self.Y))))
        output_check = '../r_array/conv_output({},{},{}).npy'.format(self.Y.shape[0],self.Y.shape[1],self.Y.shape[2])
        data_io.write(self.Y, output_check)
#         logger.info("=======================Conv Done================================")
        return self.Y


    def backward(self,DY):
        '''
        Backward-passes an input error gradient DY towards the input neurons of this layer.

        Parameters
        ----------

        DY : numpy.ndarray
            an error gradient shaped same as the output array of forward, i.e. (N,Hy,Wy,Dy) with
            N = number of samples in the batch
            Hy = heigth of the output
            Wy = width of the output
            Dy = output depth = input depth


        Returns
        -------

        DX : numpy.ndarray
            the error gradient propagated towards the input

        '''

        self.DY = DY
        N,Hy,Wy,NF = DY.shape
        hf,wf,df,NF = self.W.shape
        hstride, wstride = self.stride

        DX = np.zeros_like(self.X,dtype=np.float)


        if not (hf == wf and self.stride == (1,1)):
            for i in range(Hy):
                for j in range(Wy):
                    DX[:,i*hstride:i*hstride+hf , j*wstride:j*wstride+wf , : ] += (self.W[na,...] * DY[:,i:i+1,j:j+1,na,:]).sum(axis=4)  #sum over all the filters
        else:
            for i in range(hf):
                for j in range(wf):
                    DX[:,i:i+Hy:hstride,j:j+Wy:wstride,:] += np.dot(DY,self.W[i,j,:,:].T)

        return DX #* (hf*wf*df)**.5 / (NF*Hy*Wy)**.5


    def update(self,lrate):
        N,Hx,Wx,Dx = self.X.shape
        N,Hy,Wy,NF = self.DY.shape

        hf,wf,df,NF = self.W.shape
        hstride, wstride = self.stride

        DW = np.zeros_like(self.W,dtype=np.float)

        if not (hf == wf and self.stride == (1,1)):
            for i in range(Hy):
                for j in range(Wy):
                    DW += (self.X[:, i*hstride:i*hstride+hf , j*wstride:j*wstride+wf , :, na] * self.DY[:,i:i+1,j:j+1,na,:]).sum(axis=0)
        else:
            for i in range(hf):
                for j in range(wf):
                    DW[i,j,:,:] = np.tensordot(self.X[:,i:i+Hy:hstride,j:j+Wy:wstride,:],self.DY,axes=([0,1,2],[0,1,2]))

        DB = self.DY.sum(axis=(0,1,2))
        self.W -= lrate * DW / (hf*wf*df*Hy*Wy)**.5
        self.B -= lrate * DB / (Hy*Wy)**.5


    def clean(self):
        self.X = None
        self.Y = None
        self.Z = None
        self.DY = None


    def _simple_lrp_slow(self,R):
        '''
        LRP according to Eq(56) in DOI: 10.1371/journal.pone.0130140
        This function shows all necessary operations to perform LRP in one place and is therefore not optimized
        '''

        N,Hout,Wout,NF = R.shape
        hf,wf,df,NF = self.W.shape
        hstride, wstride = self.stride

        Rx = np.zeros_like(self.X,dtype=np.float)

        for i in range(Hout):
            for j in range(Wout):
                Z = self.W[na,...] * self.X[:, i*hstride:i*hstride+hf , j*wstride:j*wstride+wf , : , na]
                Zs = Z.sum(axis=(1,2,3),keepdims=True) + self.B[na,na,na,na,...]
                Zs += 1e-16*((Zs >= 0)*2 - 1.) # add a weak numerical stabilizer to cushion division by zero
                Rx[:,i*hstride:i*hstride+hf: , j*wstride:j*wstride+wf: , : ] += ((Z/Zs) * R[:,i:i+1,j:j+1,na,:]).sum(axis=4)
        return Rx



    def _simple_lrp(self,R):
        '''
        LRP according to Eq(56) in DOI: 10.1371/journal.pone.0130140
        '''

        N,Hout,Wout,NF = R.shape
        hf,wf,df,NF = self.W.shape
        hstride, wstride = self.stride

        Rx = np.zeros_like(self.X,dtype=np.float)
        R_norm = R / (self.Y + 1e-16*((self.Y >= 0)*2 - 1.))

        for i in range(Hout):
            for j in range(Wout):
                if self.lrp_aware:
                    Z = self.Z[:,i,j,...]
                else:
                    Z = self.W[na,...] * self.X[:, i*hstride:i*hstride+hf , j*wstride:j*wstride+wf , : , na]

                Rx[:,i*hstride:i*hstride+hf: , j*wstride:j*wstride+wf: , : ] += (Z * (R_norm[:,i:i+1,j:j+1,na,:])).sum(axis=4)
        return Rx

    def _flat_lrp(self,R):
        '''
        distribute relevance for each output evenly to the output neurons' receptive fields.
        '''

        N,Hout,Wout,NF = R.shape
        hf,wf,df,NF = self.W.shape
        hstride, wstride = self.stride

        Rx = np.zeros_like(self.X,dtype=np.float)

        for i in range(Hout):
            for j in range(Wout):
                Z = np.ones((N,hf,wf,df,NF))
                Zs = Z.sum(axis=(1,2,3),keepdims=True)

                Rx[:,i*hstride:i*hstride+hf: , j*wstride:j*wstride+wf: , : ] += ((Z/Zs) * R[:,i:i+1,j:j+1,na,:]).sum(axis=4)
        return Rx

    def _ww_lrp(self,R):
        '''
        LRP according to Eq(12) in https://arxiv.org/pdf/1512.02479v1.pdf
        '''

        N,Hout,Wout,NF = R.shape
        hf,wf,df,NF = self.W.shape
        hstride, wstride = self.stride

        Rx = np.zeros_like(self.X,dtype=np.float)

        for i in range(Hout):
            for j in range(Wout):
                Z = self.W[na,...]**2
                Zs = Z.sum(axis=(1,2,3),keepdims=True)

                Rx[:,i*hstride:i*hstride+hf: , j*wstride:j*wstride+wf: , : ] += ((Z/Zs) * R[:,i:i+1,j:j+1,na,:]).sum(axis=4)
        return Rx

    def _epsilon_lrp_slow(self,R,epsilon):
        '''
        LRP according to Eq(58) in DOI: 10.1371/journal.pone.0130140
        This function shows all necessary operations to perform LRP in one place and is therefore not optimized
        '''

        N,Hout,Wout,NF = R.shape
        hf,wf,df,NF = self.W.shape
        hstride, wstride = self.stride

        Rx = np.zeros_like(self.X,dtype=np.float)

        for i in range(Hout):
            for j in range(Wout):
                Z = self.W[na,...] * self.X[:, i*hstride:i*hstride+hf , j*wstride:j*wstride+wf , : , na]
                Zs = Z.sum(axis=(1,2,3),keepdims=True) + self.B[na,na,na,na,...]
                Zs += epsilon*((Zs >= 0)*2-1)
                Rx[:,i*hstride:i*hstride+hf: , j*wstride:j*wstride+wf: , : ] += ((Z/Zs) * R[:,i:i+1,j:j+1,na,:]).sum(axis=4)
        return Rx


    def _epsilon_lrp(self,R,epsilon):
        '''
        LRP according to Eq(58) in DOI: 10.1371/journal.pone.0130140
        '''

        N,Hout,Wout,NF = R.shape
        hf,wf,df,NF = self.W.shape
        hstride, wstride = self.stride

        Rx = np.zeros_like(self.X,dtype=np.float)
        R_norm = R / (self.Y + epsilon*((self.Y >= 0)*2 - 1.))
#         logger.info("=======================Lrp Conv Check===============================")
#         logger.info("initial Relevance is {0}".format(R.shape))
#         logger.info("initial Relevance value is : {0}".format(np.sum(~np.isnan(R))))
#         logger.info("the conv lrp X shape is {0}".format(Rx.shape))
#         logger.info("the conv lrp X shape value is : {0}".format(np.sum(~np.isnan(Rx))))
#         logger.info("the conv lrp filter size is ({},{},{},{})".format(self.fh, self.fw, self.fd, self.n))
#         logger.info("the conv lrp W shape is {0}".format(self.W.shape))
#         logger.info("the conv lrp W shape value is : {0}".format(np.sum(~np.isnan(self.W))))
#         logger.info("the conv lrp stride shape is {0}".format(self.stride))
#         logger.info("{} : {}, {} : {} ".format('lrp H',Hout,'lrp W', Wout))
        Rsave = Rx
#         logger.info("the Relavance score shape is {0}".format(R_norm.shape))
#         logger.info("the Relavance score value is : {0}".format(np.sum(~np.isnan(R_norm))))
#         logger.info("before lrp x shape is {0}".format(self.X.shape))
#         logger.info("before lrp x value is : {0}".format(np.sum(~np.isnan(self.X))))
        if Rx.shape[2] == 1:
            Rsave4 = np.reshape(Rsave, [10,10])
        elif Rx.shape[2] == 5:
            Rsave3 = np.reshape(Rsave, [25, 25])
        elif Rx.shape[2] == 14:
            Rsave2 = np.reshape(Rsave, [196, 10])
        else:
            Rsave1 = np.reshape(Rsave, [1024, 1])
        for i in range(Hout):
            for j in range(Wout):
                if self.lrp_aware:
                    Z = self.Z[:,i,j,...]
                else:
                    Z = self.W[na,...] * self.X[:, i*hstride:i*hstride+hf , j*wstride:j*wstride+wf , : , na]
                weight_lrp = Z * (R_norm[:,i:i+1,j:j+1,na,:])
#                 logger.info("during {} and {} lrp X shape is {}".format(i,j,Z.shape))
#                 logger.info("during {} and {} lrp X value is : {}".format(i,j,np.sum(~np.isnan(Z))))
#                 logger.info("during {} and {} lrp Rx shape is {}".format(i,j,Rx.shape))
#                 logger.info("during {} and {} lrp Rx value is : {}".format(i,j,np.sum(~np.isnan(Rx))))
#                 logger.info("during {} and {} weight shape is {}".format(i,j,weight_lrp.shape))
#                 logger.info("during {} and {} weight value is : {}".format(i,j,np.sum(~np.isnan(weight_lrp))))
                Rx[:,i*hstride:i*hstride+hf: , j*wstride:j*wstride+wf: , : ] += (weight_lrp).sum(axis=4)
#                 logger.info("during {} and {} lrp Rx final is {}".format(i,j,Rx.shape))
#                 logger.info("during {} and {} Rx final value is : {}".format(i,j,np.sum(~np.isnan(Rx))))
                if Rx.shape[2] == 1:
                    Rlim4 = np.reshape(Rx, [10, 10])
                    Rsave4 = np.concatenate((Rsave4, Rlim4), axis = 1)
                    Rfile4 = '../r_array/convolution_4.npy'
                    data_io.write(Rsave4, Rfile4)
                elif Rx.shape[2] == 5:
                    Rlim3 = np.reshape(Rx, [25, 25])
                    Rsave3 = np.concatenate((Rsave3, Rlim3), axis = 1)
                    Rfile3 = '../r_array/convolution_3.npy'
                    data_io.write(Rsave3, Rfile3)
                elif Rx.shape[2] == 14:
                    Rlim2 = np.reshape(Rx, [196, 10])
                    Rsave2 = np.concatenate((Rsave2, Rlim2), axis = 1)
                    Rfile2 = '../r_array/convolution_2.npy'
                    data_io.write(Rsave2, Rfile2)
                else:
                    Rlim1 = np.reshape(Rx, [1024, 1])
                    Rsave1 = np.concatenate((Rsave1, Rlim1), axis = 1)
                    Rfile1 = '../r_array/convolution_1.npy'
                    data_io.write(Rsave1, Rfile1)
#         logger.info("after conv lrp weight shape is {0}".format(weight_lrp.shape))
#         logger.info("after conv lrp weight value is : {0}".format(np.sum(~np.isnan(weight_lrp))))
        weight_l = '../r_array/x_lrp_conv_weight({},{},{}).npy'.format(weight_lrp.shape[0],weight_lrp.shape[1],weight_lrp.shape[2])
        data_io.write(weight_lrp, weight_l)
        
#         logger.info("after conv lrp tensordot X shape is {0}".format(self.X.shape))
#         logger.info("after conv lrp tensordot X value is : {0}".format(np.sum(~np.isnan(self.X))))
        x_lrp = '../r_array/x_lrp_conv_input({},{},{}).npy'.format(self.X.shape[0],self.X.shape[1],self.X.shape[2])
        data_io.write(self.X, x_lrp)
        
#         logger.info("after conv lrp output of shape is {0}".format(Rx.shape))
#         logger.info("after conv lrp output value is : {0}".format(np.sum(~np.isnan(Rx))))
        lrp_check = '../r_array/conv_lrp({},{},{}).npy'.format(Rx.shape[0],Rx.shape[1],Rx.shape[2])
        data_io.write(Rx, lrp_check)
        
        data_io.write(Rx, '../r_array/convolution.npy')
#         logger.info("=======================Lrp Conv Done===============================")
        return Rx


    def _alphabeta_lrp_slow(self,R,alpha):
        '''
        LRP according to Eq(60) in DOI: 10.1371/journal.pone.0130140
        '''

        beta = 1 - alpha

        N,Hout,Wout,NF = R.shape
        hf,wf,df,NF = self.W.shape
        hstride, wstride = self.stride

        Rx = np.zeros_like(self.X,dtype=np.float)

        for i in range(Hout):
            for j in range(Wout):
                Z = self.W[na,...] * self.X[:, i*hstride:i*hstride+hf , j*wstride:j*wstride+wf , : , na]

                if not alpha == 0:
                    Zp = Z * (Z > 0)
                    Bp = (self.B * (self.B > 0))[na,na,na,na,...]
                    Zsp = Zp.sum(axis=(1,2,3),keepdims=True) + Bp
                    Ralpha = alpha * ((Zp/Zsp) * R[:,i:i+1,j:j+1,na,:]).sum(axis=4)
                    Ralpha[np.isnan(Ralpha)] = 0
                else:
                    Ralpha = 0

                if not beta == 0:
                    Zn = Z * (Z < 0)
                    Bn = (self.B * (self.B < 0))[na,na,na,na,...]
                    Zsn = Zn.sum(axis=(1,2,3),keepdims=True) + Bn
                    Rbeta = beta * ((Zn/Zsn) * R[:,i:i+1,j:j+1,na,:]).sum(axis=4)
                    Rbeta[np.isnan(Rbeta)] = 0
                else:
                    Rbeta = 0

                Rx[:,i*hstride:i*hstride+hf: , j*wstride:j*wstride+wf: , : ] += Ralpha + Rbeta

        return Rx


    def _alphabeta_lrp(self,R,alpha):
        '''
        LRP according to Eq(60) in DOI: 10.1371/journal.pone.0130140
        '''

        beta = 1 - alpha

        N,Hout,Wout,NF = R.shape
        hf,wf,df,NF = self.W.shape
        hstride, wstride = self.stride

        Rx = np.zeros_like(self.X,dtype=np.float)

        for i in range(Hout):
            for j in range(Wout):
                if self.lrp_aware:
                    Z = self.Z[:,i,j,...]
                else:
                    Z = self.W[na,...] * self.X[:, i*hstride:i*hstride+hf , j*wstride:j*wstride+wf , : , na]

                Zplus = Z > 0 #index mask of positive forward predictions

                if alpha * beta != 0 : #the general case: both parameters are not 0
                    Zp = Z * Zplus
                    Zsp = Zp.sum(axis=(1,2,3),keepdims=True) + (self.B * (self.B > 0))[na,na,na,na,...] + 1e-16

                    Zn = Z - Zp
                    Zsn = self.Y[:,i:i+1,j:j+1,na,:] - Zsp - 1e-16

                    Rx[:,i*hstride:i*hstride+hf: , j*wstride:j*wstride+wf: , : ] += ((alpha * (Zp/Zsp) + beta * (Zn/Zsn))*R[:,i:i+1,j:j+1,na,:]).sum(axis=4)

                elif alpha: #only alpha is not 0 -> alpha = 1, beta = 0
                    Zp = Z * Zplus
                    Zsp = Zp.sum(axis=(1,2,3),keepdims=True) + (self.B * (self.B > 0))[na,na,na,na,...] + 1e-16
                    Rx[:,i*hstride:i*hstride+hf: , j*wstride:j*wstride+wf: , : ] += (Zp*(R[:,i:i+1,j:j+1,na,:]/Zsp)).sum(axis=4)

                elif beta: # only beta is not 0 -> alpha = 0, beta = 1
                    Zn = Z * np.invert(Zplus)
                    Zsn = Zn.sum(axis=(1,2,3),keepdims=True) + (self.B * (self.B < 0))[na,na,na,na,...] + 1e-16
                    Rx[:,i*hstride:i*hstride+hf: , j*wstride:j*wstride+wf: , : ] += (Zn*(R[:,i:i+1,j:j+1,na,:]/Zsn)).sum(axis=4)

                else:
                    raise Exception('This case should never occur: alpha={}, beta={}.'.format(alpha, beta))

        return Rx