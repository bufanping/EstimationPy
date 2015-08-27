import numpy as np


class ukfAugmented():
	# number of state variables, outputs and sigma points
	n_state    = 0
	n_augState = 0
	n_outputs  = 0
	n_points   = 0

	# parameters of the Unscented Kalman Filter
	alpha     = 0
	k         = 0
	beta      = 0
	lambd     = 0

	# weights of the UKF
	W_m       = np.zeros((2*n_augState + 1, 1))
	W_c       = np.zeros((2*n_augState + 1, 1))
	CstCov    = 0
	
	# parameters for the augmented version of the UKF
	alpha_q  = 0
	lambda_s = 0
	mu       = 0
	A        = 0
	minS     = 0
		
	"""
	initialization of the UKF and its parameters
	"""
	def __init__(self, n_state, n_outputs):
		# set the number of states variables and outputs
		self.n_state    = n_state
		self.n_augState = 2*n_state + n_outputs
		self.n_outputs  = n_outputs

		# compute the sigma points
		self.n_points  = 1 + 2*self.n_augState

		# define UKF parameters
		self.setUKFparams()

		# compute the weights
		self.computeWeights()
		
		# set parameters for the Augmented UKF modified version
		self.setAugmentedPars(0.995, 1/np.sqrt(3.0), 0.1*np.diag(np.ones(self.n_state)))

	"""
	This method set the default parameters of the filter
	"""
	def setDefaultUKFparams(self):
		self.alpha    = 0.01
		self.k        = 0
		self.beta     = 2
		self.lambd    = (self.alpha**2)*(self.n_augState + self.k) - self.n_augState
		self.sqrtC    = self.alpha*np.sqrt(self.n_augState + self.k)

	"""
	This method set the non default parameters of the filter
	"""
	def setUKFparams(self, alpha = 1.0/np.sqrt(3.0), beta = 2, k=None):
		self.alpha     = alpha
		self.beta      = beta

		if k == None:
			self.k = 3 - self.n_augState
		else:
			self.k = k
		
		self.lambd    = (self.alpha**2)*(self.n_augState + self.k) - self.n_augState
		self.sqrtC    = self.alpha*np.sqrt(self.k + self.n_augState)	

	"""
	This method set the parameters for the augmented version of the filter
	"""
	def setAugmentedPars(self, alpha=0.99, mu= 1.0/np.sqrt(3.0), minS=0.0):
		# decay of the initial covariance
		self.alpha_q = alpha
		
		# growth of the computed covariance
		self.lambda_s = alpha
		
		# final value for the weight of the computed covariance
		self.mu       = mu
		self.A        = (1 - self.lambda_s)*self.mu
		
		# minimum covariance matrix allowed
		self.minS     = minS

	"""
	This method computes the weights (both for covariance and mean value computation) of the UKF filter
	"""
	def computeWeights(self):
		self.W_m       = np.zeros((1+self.n_augState*2,1))
		self.W_c       = np.zeros((1+self.n_augState*2,1))
		
		self.W_m[0,0]  = self.lambd/(self.n_augState + self.lambd)
		self.W_c[0,0]  = self.lambd/(self.n_augState + self.lambd) + (1 - self.alpha**2 + self.beta)

		for i in range(2*self.n_augState):
			self.W_m[i+1,0] = 1.0/(2.0*(self.n_augState + self.lambd))
			self.W_c[i+1,0] = 1.0/(2.0*(self.n_augState + self.lambd))
	
	"""
	comnputes the matrix of sigma points, given the square root of the covariance matrix
	and the previous state vector
	"""
	def computeSigmaPoints(self,x,sqrtP):
		
		# reshape the state vector
		x = x.reshape(1,self.n_augState)

		# initialize the matrix of sigma points
		# the result is
		# [[0.0, 0.0, 0.0],
		#  [0.0, 0.0, 0.0],
		#  [0.0, 0.0, 0.0],
		#  [0.0, 0.0, 0.0],
		#      ....
		#  [0.0, 0.0, 0.0]]
		Xs      = np.zeros((self.n_points,self.n_augState))

		# Now using the sqrtP matrix that is lower triangular, I create the sigma points
		# by adding and subtracting the rows of the matrix sqrtP, to the lines of Xs
		# [[s11, 0  , 0  ],
		#  [s12, s22, 0  ],
		#  [s13, s23, s33]]
		i = 1
		Xs[0,:] = x
		for row in sqrtP:
			Xs[i,:]                 = x + self.sqrtC*row
			Xs[i+self.n_augState,:] = x - self.sqrtC*row
			i += 1
		
		return Xs
	
	"""
	This function computes the state evolution x_old -> x_new
	x_new = f(x_old, ...)
	"""
	def stateEvolution(self,m,x,u_old,t_old):
		return m.functionF(x,u_old,t_old)

	"""
	This function computes the output evolution x -> y
	y = f(x, ...)
	"""
	def outputMeasurement(self,m,x,u,t):
		return m.functionG(x,u,t)

	"""
	This function computes the state evolution of all the sigma points through the model
	"""
	def sigmaPointProj(self,m,Xs,u_old,u,t_old,t):
		# initialize the vector of the NEW STATES
		X_proj = np.zeros((self.n_points,self.n_state))
		
		j = 0
		for x in Xs:
			processNoise =  x[self.n_state:2*self.n_state]
			X_proj[j,:] = m.functionF(x,u_old,u,t_old,t,False) + processNoise
			j += 1
		return X_proj

	"""
	This function computes the output measurement of all the sigma points through the model
	"""
	def sigmaPointOutProj(self,m,Xs,u,t):
		# initialize the vector of the outputs
		Z_proj = np.zeros((self.n_points,self.n_outputs))
		j = 0
		for x in Xs:
			outputNoise = x[2*self.n_state:]
			Z_proj[j,:] = m.functionG(x,u,t,False) + outputNoise
			j += 1
		return Z_proj

	"""
	This function computes the average of the sigma point evolution
	"""
	def averageProj(self,X_proj):
		# make sure that the stape is [1+2*n, n]
		X_proj.reshape(1+self.n_augState*2, self.n_state)
		
		# dot product of the two matrices
		avg = np.dot(self.W_m.T, X_proj)
		return avg
	
	"""
	This function computes the average of the sigma point outputs
	"""
	def averageOutProj(self,Z_proj):
		# make sure that the stape is [1+2*n, n]
		Z_proj.reshape(1+self.n_augState*2, self.n_outputs)
		
		# dot product of the two matrices
		avg = np.dot(self.W_m.T, Z_proj)
		return avg
	
	"""
	This function computes the squared covariance matrix using QR decomposition + a Cholesky update
	"""
	def computeS(self,X_proj,Xave,sqrtQ=None):
		
		weights = np.sqrt( np.abs(self.W_c[:,0]) )
		signs   = np.sign( self.W_c[:,0] )
		
		A     = np.array([[]])
		i     = 0
		for x in X_proj:
			error = signs[i]*weights[i]*(x - Xave)
			if i==1:
				A = error.T
			elif i>1:
				A = np.hstack((A,error.T))
			i    += 1
			
		if sqrtQ != None:
			A = np.hstack((A,sqrtQ))
		
		q,L = np.linalg.qr(A.T,mode='full')

		# NOW START THE CHOLESKY UPDATE
		x = signs[0]*weights[0]*(X_proj[0,] - Xave)
				
		L = self.cholUpdate(L,x.T,self.W_c[:,0])
		
		return L
		
	"""
	This function computes the squared covariance matrix using QR decomposition + a Cholesky update
	"""
	def computeSy(self,Z_proj,Zave,sqrtR = None):
		
		weights = np.sqrt( np.abs(self.W_c[:,0]) )
		signs   = np.sign( self.W_c[:,0] )
		
		A     = np.array([[]])
		i     = 0
		for z in Z_proj:
			error = signs[i]*weights[i]*(z - Zave)
			if i==1:
				A = error.T
			elif i>1:
				A = np.hstack((A,error.T))
			i    += 1
			
		if sqrtR != None:
			A = np.hstack((A,sqrtR))
		
		q,L = np.linalg.qr(A.T,mode='full')

		# NOW START THE CHOLESKY UPDATE
		z = signs[0]*weights[0]*(Z_proj[0,] - Zave)
		
		L = self.cholUpdate(L,z.T,self.W_c[:,0])
		
		return L
	
	"""
	This function computes the state-output cross covariance matrix (between X and Z)
	"""
	def computeCovXZ(self,X_p, Xa, Z_p, Za):
		W = np.diag(self.W_c[:,0]).reshape(self.n_points,self.n_points)
		
		Vx = np.zeros(X_p.shape)
		for j in range(self.n_points):
			Vx[j,:]   = X_p[j,:] - Xa[0]	
		
		Vz = np.zeros(Z_p.shape)
		for j in range(self.n_points):
			Vz[j,:]   = Z_p[j,:] - Za[0]
	
		CovXZ = np.dot(np.dot(Vx.T,W),Vz)
		return CovXZ
	
	"""
	This function copmputes the Cholesky update
	"""
	def cholUpdate(self,L,X,W):
	
		L = L.copy()
		weights = np.sqrt( np.abs( W ) )
		signs   = np.sign( W )
	
		# NOW START THE CHOLESKY UPDATE
		# DO IT FOR EACH COLUMN IN THE X MATRIX
		
		(row, col) = X.shape
		
		for j in range(col):
			x = X[0:,j]
			
			for k in range(row):
				rr_arg    = L[k,k]**2 + signs[0]*x[k]**2
				rr        = 0.0 if rr_arg < 0 else np.sqrt(rr_arg)
				c         = rr / L[k,k]
				s         = x[k] / L[k,k]
				L[k,k]    = rr
				L[k,k+1:] = (L[k,k+1:] + signs[0]*s*x[k+1:])/c
				x[k+1:]   = c*x[k+1:]  - s*L[k, k+1:]
				
		return L
	
	"""
	This function computes the state-state cross covariance matrix (between Xold and Xnew)
	This is used in the smoothing process
	"""
	def computeCxx(self,X_next,Xave_next,X_now,Xave_now):
		W = np.diag(self.W_c[:,0]).reshape(self.n_points,self.n_points)
		
		Vnext = np.zeros(X_next.shape)
		for j in range(self.n_points):
			Vnext[j,:]   = X_next[j,:] - Xave_next[0]	
		
		Vnow = np.zeros(X_now.shape)
		for j in range(self.n_points):
			Vnow[j,:]   = X_now[j,:] - Xave_now[0]
	
		Cxx = np.dot(np.dot(Vnext.T,W),Vnow)
		return Cxx

	"""
	function call for prediction + update of the UKF
	"""
	def ukfAugmented_step(self,z,x,S,Sq,Sr,alpha_s,u_old,u,t_old,t,m,verbose=False,adaptive=False):		
		
		# augmented state variables
		x_Aug = np.hstack((x, np.zeros(self.n_state), np.zeros(self.n_outputs)))
		
		# iterative weight of the computed covariance Sx		
		alpha_s  = (alpha_s*self.lambda_s + self.A)
		
		if not adaptive:
			actualSq = Sq
		else:
			# actual value of the process covariance
			actualSq = Sq + alpha_s*S
			if np.linalg.norm(actualSq,2) <= np.linalg.norm(self.minS,2):
				actualSq = self.minS
			# back propagate the initial squared covariance, reduced by alpha_q
			Sq      = self.alpha_q*Sq
		
		# augmented square covariance matrix
		S_1   = np.hstack((S, 									     np.zeros((self.n_state, self.n_state)),	np.zeros((self.n_state, self.n_outputs))))
		S_2   = np.hstack((np.zeros((self.n_state, self.n_state)),   actualSq,						      	    np.zeros((self.n_state, self.n_outputs))))
		S_3   = np.hstack((np.zeros((self.n_outputs, self.n_state)), np.zeros((self.n_outputs, self.n_state)), 	Sr))
		S_Aug = np.vstack((S_1, S_2, S_3))
		
		# the list of sigma points (each signa point can be an array, the state variables)
		Xs      = self.computeSigmaPoints(x_Aug,S_Aug)
		if verbose:
			print "Sigma Points"
			print Xs
	
		# compute the projected (state) points (each sigma points is propagated through the state transition function)
		X_proj = self.sigmaPointProj(m,Xs,u_old,u,t_old,t)
		if verbose:
			print "Projection of sigma points"
			print X_proj
	
		# compute the average
		Xave = self.averageProj(X_proj)
		if verbose:
			print "averaged projection"
			print Xave
		
		# compute the new squared covariance matrix S
		Snew = self.computeS(X_proj,Xave)
		if verbose:
			print "Square root matrix of x"
			print Snew

		# compute the projected (outputs) points (each sigma points is propagated through the state transition function)
		Z_proj = self.sigmaPointOutProj(m,Xs,u,t)
		if verbose:
			print "Output projections"
			print Z_proj

		# compute the average output
		Zave = self.averageOutProj(Z_proj)
		if verbose:
			print "Average output projection"
			print Zave
		
		# compute the innovation covariance (relative to the output)
		Sy = self.computeSy(Z_proj,Zave)
		if verbose:
			print "Square root matrix of y"
			print Sy
		
		# compute the cross covariance matrix
		CovXZ = self.computeCovXZ(X_proj, Xave, Z_proj, Zave)
		if verbose:
			print "Covariance matrix between x and y"
			print CovXZ
		
		# Data assimilation step
		# The information obtained in the prediction step are corrected with the information
		# obtained by the measurement of the outputs
		
		firstDivision = np.linalg.lstsq(Sy.T,CovXZ.T)[0]
		K             = np.linalg.lstsq(Sy, firstDivision)[0]
		K             = K.T
		
		X_corr = Xave + np.dot(K,z.reshape(self.n_outputs,1)-Zave.T).T
		U      = np.dot(K,Sy)
		S_corr = self.cholUpdate(Snew,U,-1*np.ones(self.n_state))

		return (X_corr, S_corr.T, Zave, Sy.T, Sq, alpha_s)
	
	"""
	This method returns the smoothed state estimation
	"""
	def smoothAugmented(self,time,Xhat,S,sqrtQ,U,m):
		
		# initialize the smoothed states and covariance matrix
		# the initial value of the smoothed state estimation are equal to the filtered ones
		Xsmooth = Xhat.copy()
		Ssmooth = S.copy()
		
		# get the number of time steps		
		s = np.reshape(time,(-1,1)).shape
		nTimeStep = s[0]

		# iterating starting from the end and back
		# i : nTimeStep-2 -> 0
		#
		# From point i with an estimation Xave[i], and S[i]
		# new sigma points are created and propagated, the result is a 
		# new vector of states X[i+1] (one for each sigma point)
		#
		# NOTE that at time i+1 there is available a corrected estimation of the state Xcorr[i+1]
		# thus the difference between these two states is backpropagated to the state at time i
		for i in range(nTimeStep-2,-1,-1):
		
			# actual state estimation and covariance matrix
			x_i = Xsmooth[i,:]
			S_i = Ssmooth[i,:,:]

			# compute the sigma points
			Xs_i        = self.computeSigmaPoints(x_i,S_i)
			# mean of the sigma points
			Xs_i_ave    = self.averageProj(Xs_i)
			# propagate the sigma points
			x_plus_1    = self.sigmaPointProj(m,Xs_i,U[i],time[i])
			# average of the sigma points
			Xave_plus_1 = self.averageProj(x_plus_1)
			# compute the new covariance matrix
			Snew = self.computeS(x_plus_1,Xave_plus_1,sqrtQ)
			
			# compute the cross covariance matrix of the two states
			# (new state already corrected, coming from the "future", and the new just computed through the projection)
			Cxx  = self.computeCxx(x_plus_1,Xave_plus_1,Xs_i,Xs_i_ave)

			# gain for the back propagation
			firstDivision = np.linalg.lstsq(Snew.T, Cxx.T)[0]
			D             = np.linalg.lstsq(Snew, firstDivision)[0]
			D             = D.T
			
			# correction (i.e. smoothing, of the state estimation and covariance matrix)
			Xsmooth[i,:]   = Xhat[i,:] + np.dot(D, Xsmooth[i+1,:] - Xave_plus_1[0])
			V              = np.dot(D,Ssmooth[i+1,:,:] - Snew)
			Ssmooth[i,:,:] = self.cholUpdate(S[i,:,:],V,-1*np.ones(self.n_state))
			
		return (Xsmooth, Ssmooth)